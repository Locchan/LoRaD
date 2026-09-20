FROM docker.io/library/nginx:stable-alpine

RUN rm -rf /usr/share/nginx/html/* && mkdir -p /usr/share/nginx/html/ui

COPY css /usr/share/nginx/html/ui/css
COPY js /usr/share/nginx/html/ui/js
COPY randomBackground /usr/share/nginx/html/ui/randomBackground
COPY index.html favicon.ico logo.png news.mp4 /usr/share/nginx/html/ui/
COPY nginx.conf /etc/nginx/conf.d/lorad.conf
COPY apply-config.sh /tmp/apply-config.sh

ARG LORAD_ENV=development
ARG LORAD_DOMAIN=
ARG LORAD_SCHEME=
ARG LORAD_API_PATH=
ARG LORAD_RADIO_PATH=
ARG LORAD_API_URL=
ARG LORAD_RADIO_URL=
ARG LORAD_WS_PATH=
ARG LORAD_WS_URL=

RUN LORAD_ENV="$LORAD_ENV" \
    LORAD_DOMAIN="$LORAD_DOMAIN" \
    LORAD_SCHEME="$LORAD_SCHEME" \
    LORAD_API_PATH="$LORAD_API_PATH" \
    LORAD_RADIO_PATH="$LORAD_RADIO_PATH" \
    LORAD_WS_PATH="$LORAD_WS_PATH" \
    LORAD_API_URL="$LORAD_API_URL" \
    LORAD_RADIO_URL="$LORAD_RADIO_URL" \
    LORAD_WS_URL="$LORAD_WS_URL" \
    sh /tmp/apply-config.sh /usr/share/nginx/html/ui/js/config.js \
 && rm -f /tmp/apply-config.sh

EXPOSE 5477

CMD ["nginx", "-g", "daemon off;"]
