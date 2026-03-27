FROM nginx:1.27-alpine

COPY nginx.http.conf /etc/nginx/nginx.http.conf
COPY nginx.tls.conf /etc/nginx/nginx.tls.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
