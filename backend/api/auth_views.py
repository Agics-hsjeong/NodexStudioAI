import base64
import hashlib
import json
import secrets
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core import signing
from django.http import HttpResponseRedirect
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken


@api_view(["POST"])
@permission_classes([AllowAny])
def dev_login(request):
    """
    개발용 로그인 엔드포인트.
    body: { username, password }
    - 사용자가 없으면 생성
    - 있으면 비밀번호 검증
    """
    username = str(request.data.get("username") or "").strip()
    password = str(request.data.get("password") or "").strip()
    if not username or not password:
        return Response(
            {"error": {"code": "INVALID_INPUT", "message": "username/password required"}},
            status=400,
        )

    User = get_user_model()
    user = User.objects.filter(username=username).first()
    if user is None:
        user = User.objects.create(
            username=username,
            password=make_password(password),
        )
    elif not user.check_password(password):
        # 개발 편의: 기존 계정이면 입력 비밀번호로 재설정
        user.password = make_password(password)
        user.save(update_fields=["password"])

    refresh = RefreshToken.for_user(user)
    return Response(
        {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": {"id": user.id, "username": user.username},
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    return Response({"user": {"id": request.user.id, "username": request.user.username}})


def _google_cfg():
    from django.conf import settings

    client_id = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "")
    client_secret = getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "")
    redirect_uri = getattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", "")
    return client_id, client_secret, redirect_uri


def _sanitize_username(raw: str) -> str:
    safe = "".join(ch for ch in raw if ch.isalnum() or ch in {"_", "-", "."})
    safe = safe.strip("._-")
    return safe[:120] or "google_user"


@api_view(["GET"])
@permission_classes([AllowAny])
def google_start(request):
    client_id, _, redirect_uri = _google_cfg()
    if not client_id or not redirect_uri:
        return Response(
            {"error": {"code": "OAUTH_NOT_CONFIGURED", "message": "google oauth env not configured"}},
            status=500,
        )

    nonce = base64.urlsafe_b64encode(hashlib.sha256(secrets.token_bytes(32)).digest())[:32].decode("ascii")
    state = signing.dumps({"nonce": nonce}, salt="google-oauth-state")
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
            "nonce": nonce,
        }
    )
    return HttpResponseRedirect(f"https://accounts.google.com/o/oauth2/v2/auth?{query}")


@api_view(["GET"])
@permission_classes([AllowAny])
def google_callback(request):
    err = request.query_params.get("error")
    if err:
        return Response({"error": {"code": "GOOGLE_OAUTH_ERROR", "message": str(err)}}, status=400)

    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code or not state:
        return Response(
            {"error": {"code": "INVALID_CALLBACK", "message": "code/state required"}},
            status=400,
        )

    try:
        signing.loads(state, salt="google-oauth-state", max_age=600)
    except Exception:
        return Response(
            {"error": {"code": "INVALID_STATE", "message": "state validation failed"}},
            status=400,
        )

    client_id, client_secret, redirect_uri = _google_cfg()
    if not client_id or not client_secret or not redirect_uri:
        return Response(
            {"error": {"code": "OAUTH_NOT_CONFIGURED", "message": "google oauth env not configured"}},
            status=500,
        )

    token_body = urlencode(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    token_req = Request(
        "https://oauth2.googleapis.com/token",
        data=token_body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(token_req, timeout=10) as r:
            token_data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return Response(
            {"error": {"code": "TOKEN_EXCHANGE_FAILED", "message": "google token exchange failed"}},
            status=502,
        )

    access_token = token_data.get("access_token")
    if not access_token:
        return Response(
            {"error": {"code": "TOKEN_EXCHANGE_FAILED", "message": "missing google access token"}},
            status=502,
        )

    userinfo_req = Request(
        "https://openidconnect.googleapis.com/v1/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )
    try:
        with urlopen(userinfo_req, timeout=10) as r:
            profile = json.loads(r.read().decode("utf-8"))
    except Exception:
        return Response(
            {"error": {"code": "USERINFO_FAILED", "message": "google userinfo failed"}},
            status=502,
        )

    sub = str(profile.get("sub") or "").strip()
    email = str(profile.get("email") or "").strip()
    preferred_username = _sanitize_username(email.split("@")[0] if email else f"google_{sub[:12]}")
    if not sub:
        return Response(
            {"error": {"code": "INVALID_PROFILE", "message": "google profile missing sub"}},
            status=502,
        )

    User = get_user_model()
    user = User.objects.filter(username=preferred_username).first()
    if user is None:
        user = User.objects.create(
            username=preferred_username,
            email=email[:254],
            password=make_password(secrets.token_urlsafe(24)),
        )
    elif email and user.email != email:
        user.email = email[:254]
        user.save(update_fields=["email"])

    refresh = RefreshToken.for_user(user)
    front_base = str(getattr(django_settings, "FRONTEND_PUBLIC_URL", "") or "").strip()
    if not front_base:
        front_base = f"{request.scheme}://{request.get_host()}/"
    if not front_base.endswith("/"):
        front_base = f"{front_base}/"
    fragment = urlencode(
        {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "uid": str(user.id),
            "username": user.username,
        }
    )
    return HttpResponseRedirect(f"{front_base}#{fragment}")

