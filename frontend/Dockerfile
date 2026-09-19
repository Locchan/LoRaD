FROM docker.io/library/nginx:stable-alpine

RUN rm -rf /usr/share/nginx/html/* && mkdir -p /usr/share/nginx/html/ui

COPY css /usr/share/nginx/html/ui/css
COPY js /usr/share/nginx/html/ui/js
COPY randomBackground /usr/share/nginx/html/ui/randomBackground
COPY index.html favicon.ico logo.png news.mp4 /usr/share/nginx/html/ui/
COPY nginx.conf /etc/nginx/conf.d/lorad.conf

EXPOSE 5477

CMD ["nginx", "-g", "daemon off;"]
