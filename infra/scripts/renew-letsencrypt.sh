#!/usr/bin/env sh
set -e
cd "$(dirname "$0")/../.."

docker compose --profile cert run --rm certbot renew \
  --non-interactive \
  --webroot -w /var/www/certbot
docker compose exec nginx nginx -s reload

echo "갱신 완료."
