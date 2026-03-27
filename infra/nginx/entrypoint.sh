#!/bin/sh
set -e
CERT="/etc/letsencrypt/live/www.nodexstudio.kro.kr/fullchain.pem"
if [ -f "$CERT" ]; then
  cp /etc/nginx/nginx.tls.conf /etc/nginx/nginx.conf
else
  cp /etc/nginx/nginx.http.conf /etc/nginx/nginx.conf
fi
exec nginx -g "daemon off;"
