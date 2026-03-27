#!/usr/bin/env sh
# 사용 전: DNS가 서버 공인 IP를 가리키고, 80 포트가 열려 있어야 합니다.
# .env에 CERTBOT_EMAIL 이 설정되어 있어야 합니다.
#
# kro.kr 등 무료 공유 도메인은 Let's Encrypt "등록 도메인당 주간 50장" 한도를
# 전 세계 사용자가 같은 kro.kr 로 나눠 쓰기 때문에 자주 걸립니다.
# 한도 초과 시: retry after 시간 이후 재시도, 또는 본인 소유 도메인 사용, 또는
# 테스트만 .env 에 CERTBOT_STAGING=1 로 스테이징 인증서(브라우저 비신뢰) 발급.
#
# "Invalid port in redirect target ... 8188" / 사설 IP 리다이렉트:
# 인터넷에서 http://도메인:80/.well-known/... 요청이 https://192.168.x.x:8188/ 등으로
# 돌아가면 검증 실패입니다. 공유기·DDNS·상위 프록시가 80을 아닌 주소로 돌리지 않게 하고,
# 가능하면 호스트 NGINX_HTTP_PORT=80 (또는 외부 80 → 내부 80/443만 포워딩)을 권장합니다.

set -e
cd "$(dirname "$0")/../.."

if [ ! -f .env ]; then
  echo "프로젝트 루트에 .env 가 필요합니다."
  exit 1
fi

set -a
# shellcheck disable=SC1091
. ./.env
set +a

# CRLF·공백 제거
CERTBOT_EMAIL=$(printf '%s' "${CERTBOT_EMAIL:-}" | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

if [ -z "$CERTBOT_EMAIL" ] || [ "$CERTBOT_EMAIL" = "." ]; then
  echo "CERTBOT_EMAIL 을 .env 에 실제 이메일로 설정하세요. (비어 있으면 Certbot이 대화형으로 멈춥니다)"
  exit 1
fi

case "$CERTBOT_EMAIL" in
  *@?*.?*) ;;
  *)
    echo "CERTBOT_EMAIL 형식이 올바르지 않습니다: [$CERTBOT_EMAIL]"
    exit 1
    ;;
esac

# Let's Encrypt ACME 는 example.com / test.com 등 문서용·가짜 도메인 메일을 거절합니다.
case "$CERTBOT_EMAIL" in
  *@example.com|*@example.org|*@example.net|*@test.com|*@localhost|change-me@*|you@example.com)
    echo "CERTBOT_EMAIL 을 Gmail 등 본인이 실제로 받는 주소로 바꾸세요."
    echo "(Let's Encrypt 가 change-me@example.com / *@example.com 을 허용하지 않습니다.)"
    exit 1
    ;;
esac

if [ "${NGINX_HTTP_PORT:-80}" != "80" ]; then
  echo "주의: 호스트 HTTP 포트가 80이 아닙니다 (NGINX_HTTP_PORT=${NGINX_HTTP_PORT:-80})."
  echo "Let's Encrypt HTTP-01 은 인터넷에서 도메인:80 으로 들어와야 합니다."
  echo "공유기/방화벽에서 외부 80 -> 이 PC ${NGINX_HTTP_PORT:-80} 포워딩을 설정하거나, 호스트 nginx 는 infra/nginx/host-forward-80.example.conf 처럼 127.0.0.1 로 프록시하세요."
fi

# 기본: www + api 만 (apex nodexstudio.kro.kr 은 DNS A 없으면 NXDOMAIN → 제외)
CERTBOT_DOMAINS=$(printf '%s' "${CERTBOT_DOMAINS:-www.nodexstudio.kro.kr,api.nodexstudio.kro.kr}" | tr -d '\r')
DOMAIN_ARGS=
for d in $(echo "$CERTBOT_DOMAINS" | tr ',' ' '); do
  d=$(echo "$d" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
  [ -z "$d" ] && continue
  DOMAIN_ARGS="$DOMAIN_ARGS -d $d"
done
if [ -z "$DOMAIN_ARGS" ]; then
  echo "CERTBOT_DOMAINS 가 비어 있습니다."
  exit 1
fi
echo "인증서 SAN 도메인:$DOMAIN_ARGS"

docker compose up -d --build nginx

STAGING_ARGS=
if [ "${CERTBOT_STAGING:-0}" = "1" ] || [ "${CERTBOT_STAGING:-}" = "true" ]; then
  STAGING_ARGS="--staging"
  echo "CERTBOT_STAGING 활성화: 스테이징 CA(브라우저 경고·운영 부적합). 한도/연동 테스트용."
fi

echo ""
echo "=== HTTP-01 사전 점검 (Location 에 192.168.x / :8188 이 보이면 DNS·공유기·앞단 서버가 잘못된 리다이렉트를 넣는 것입니다) ==="
FIRST_DOM=$(echo "$CERTBOT_DOMAINS" | cut -d, -f1 | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
PREFLIGHT_HDR=
if [ -n "$FIRST_DOM" ]; then
  echo "요청: http://${FIRST_DOM}/.well-known/acme-challenge/ping (파일 없어도 404면 이 PC의 Docker nginx까지 도달)"
  PREFLIGHT_HDR=$(curl -sS -m 25 -D - -o /dev/null "http://${FIRST_DOM}/.well-known/acme-challenge/ping" 2>/dev/null) || PREFLIGHT_HDR=""
  echo "$PREFLIGHT_HDR" | head -n 30
  LOC=$(echo "$PREFLIGHT_HDR" | grep -i '^Location:' | head -n 1 || true)
  SRV=$(echo "$PREFLIGHT_HDR" | grep -i '^Server:' | head -n 1 || true)
  # Ubuntu 패키지 nginx 는 보통 "nginx/x.x.x (Ubuntu)" — Docker 이미지는 "(Ubuntu)" 없음
  case "$SRV" in
    *Ubuntu*)
      echo ""
      echo "참고: 응답 Server 가 Ubuntu 패키지 nginx 입니다. 이 저장소의 Docker nginx(알파인)와 다르면,"
      echo "      DNS A 레코드가 지금 이 PC가 아니라 다른 VPS/공유기 웹서버를 가리키는 것입니다."
      ;;
  esac
  BAD_LOC=
  # 사설·링크로컬 등(LE 가 따라가도 실패)
  if echo "$LOC" | grep -qiE 'https?://(192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.|127\.)'; then
    BAD_LOC=1
  fi
  # Location 에 명시 포트가 있고 80·443 이 아니면 LE 가 거부(예: :8188)
  if echo "$LOC" | grep -qiE 'https?://[^[:space:]/]+:[0-9]+'; then
    if ! echo "$LOC" | grep -qiE ':(80|443)(/|$)'; then
      BAD_LOC=1
    fi
  fi
  if [ -n "$BAD_LOC" ]; then
    echo ""
    echo "중단: Location 이 사설 IP 또는 Let's Encrypt 가 허용하지 않는 포트(80·443 외)로 가리킵니다."
    echo "  $LOC"
    echo ""
    echo "원인(요약): 인터넷에서 보면 도메인은 공인 IP(예: VPS)로 가는데, 그 서버가 302 로 집 안 사설망(192.168.x)으로"
    echo "  돌려 보냅니다. 이 PC에서 docker/nginx 를 아무리 고쳐도 DNS 가 그 VPS 를 가리키는 한 Certbot 은 실패합니다."
    echo ""
    if command -v dig >/dev/null 2>&1; then
      echo "지금 도메인 $FIRST_DOM 의 DNS A 레코드:"
      dig +short "$FIRST_DOM" A 2>/dev/null | sed 's/^/  /' || true
      ACOUNT=$(dig +short "$FIRST_DOM" A 2>/dev/null | grep -cE '^[0-9.]+$' || true)
      if [ "${ACOUNT:-0}" -gt 1 ] 2>/dev/null; then
        echo ""
        echo "경고: A 레코드가 ${ACOUNT}개입니다. 검증기가 매번 다른 IP로 붙을 수 있어 ACME 가 불안정합니다."
        echo "      가능하면 공인 IP 를 하나만 남기거나, 두 IP 모두에서 동일하게 80·ACME 가 열려 있어야 합니다."
      fi
    fi
    echo ""
    echo "조치: (1) 도메인 A 레코드를 이 docker compose 가 돌아가는 머신의 공인 IP 로 바꾸거나,"
    echo "       (2) 지금 DNS 가 가리키는 그 서버에 SSH 해서 nginx 에서 return 302 https://192.168... 제거,"
    echo "       (3) 또는 HTTP-01 없이 발급: ./infra/scripts/init-letsencrypt-dns01.sh (DNS 패널에 TXT 수동)"
    exit 1
  fi
  [ -z "$PREFLIGHT_HDR" ] && echo "(curl 실패: DNS 미설정·방화벽·오프라인 등)"
fi
echo "================================================================"
echo ""

docker compose --profile cert run --rm certbot certonly \
  --non-interactive \
  $STAGING_ARGS \
  --webroot -w /var/www/certbot \
  $DOMAIN_ARGS \
  --email "$CERTBOT_EMAIL" \
  --agree-tos \
  --no-eff-email

docker compose restart nginx

echo "완료. https://www.nodexstudio.kro.kr/ 로 접속해 보세요."
if [ -n "$STAGING_ARGS" ]; then
  echo "스테이징 인증서 발급됨. 운영 신뢰 인증서는 CERTBOT_STAGING=0 으로 다시 발급하세요."
fi
