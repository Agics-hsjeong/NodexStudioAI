#!/usr/bin/env sh
# HTTP-01 이 불가능할 때 사용: DNS-01(수동 TXT 레코드).
# 예: 도메인 A 가 다른 VPS 를 가리키며 그곳 nginx 가 http:// 를 https://192.168.x:8188 으로 302 하는 경우 —
#     포트 80 경로를 고치지 않아도, kro.kr DNS 관리 화면에 _acme-challenge.* TXT 만 넣으면 인증서 발급 가능.
#
# 주의:
# - Certbot 을 실행하는 이 PC(또는 서버)의 Docker 볼륨에 인증서가 저장됩니다. 운영 nginx 가 여기서 떠 있어야 합니다.
# - 브라우저 트래픽은 여전히 A 레코드가 가리키는 IP 로 갑니다. 최종적으로 A 를 이 머신 공인 IP 로 맞추거나,
#   이 머신에서 서비스할 계획이어야 https 가 의미 있습니다.
#
# 사용: 프로젝트 루트에서 ./infra/scripts/init-letsencrypt-dns01.sh  (대화형, -it 필요)
#
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

CERTBOT_EMAIL=$(printf '%s' "${CERTBOT_EMAIL:-}" | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

if [ -z "$CERTBOT_EMAIL" ] || [ "$CERTBOT_EMAIL" = "." ]; then
  echo "CERTBOT_EMAIL 을 .env 에 설정하세요."
  exit 1
fi

case "$CERTBOT_EMAIL" in
  *@?*.?*) ;;
  *)
    echo "CERTBOT_EMAIL 형식이 올바르지 않습니다: [$CERTBOT_EMAIL]"
    exit 1
    ;;
esac

case "$CERTBOT_EMAIL" in
  *@example.com|*@example.org|*@example.net|*@test.com|*@localhost|change-me@*|you@example.com)
    echo "CERTBOT_EMAIL 을 실제로 받는 주소로 바꾸세요."
    exit 1
    ;;
esac

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

STAGING_ARGS=
if [ "${CERTBOT_STAGING:-0}" = "1" ] || [ "${CERTBOT_STAGING:-}" = "true" ]; then
  STAGING_ARGS="--staging"
  echo "CERTBOT_STAGING: 스테이징 CA (브라우저 비신뢰)."
fi

echo ""
echo "=== DNS-01 수동 인증 ==="
echo "인증서 SAN:$DOMAIN_ARGS"
echo "live 경로는 nginx entrypoint 와 맞추기 위해 --cert-name www.nodexstudio.kro.kr 을 사용합니다."
echo ""
echo "── Certbot 이 요구하는 이름(예) ──"
echo "  _acme-challenge.api.nodexstudio.kro.kr   → TXT"
echo "  _acme-challenge.www.nodexstudio.kro.kr   → TXT"
echo ""
echo "── DNS 패널(존이 nodexstudio.kro.kr 일 때 흔한 입력) ──"
echo "  유형 TXT, 호스트/이름 필드에 아래처럼 (도메인 접미사는 패널이 붙임):"
echo "    _acme-challenge.api"
echo "    _acme-challenge.www"
echo "  값: Certbot 이 출력하는 한 줄 문자열 (따옴표 없음)."
echo "  잘못 예: 호스트에 api 만, 또는 전체 FQDN 을 한 덩어리로 넣어 이중 접미사가 되는 경우."
echo ""
echo "── Enter 전에 확인 (NXDOMAIN 이면 아직 레코드가 없거나 이름 오류): ──"
echo "  dig +short TXT _acme-challenge.api.nodexstudio.kro.kr @8.8.8.8"
echo "  dig +short TXT _acme-challenge.www.nodexstudio.kro.kr @8.8.8.8"
echo ""
echo "Certbot 이 두 번째 TXT 를 요구하면 첫 번째 TXT 는 지우지 말고 그대로 둔 채 두 번째만 추가합니다."
echo ""

docker compose up -d --build nginx

docker compose --profile cert run --rm -it certbot certonly \
  --manual \
  --preferred-challenges dns \
  --cert-name www.nodexstudio.kro.kr \
  $STAGING_ARGS \
  $DOMAIN_ARGS \
  --email "$CERTBOT_EMAIL" \
  --agree-tos \
  --no-eff-email

docker compose restart nginx

echo ""
echo "완료. https://www.nodexstudio.kro.kr/ 접속을 확인하세요. (A 레코드가 이 서버를 가리켜야 합니다.)"
if [ -n "$STAGING_ARGS" ]; then
  echo "스테이징이었다면 운영 발급 시 CERTBOT_STAGING=0 으로 다시 실행하세요."
fi
