FROM docker.io/library/node:22-alpine AS builder

WORKDIR /app
RUN npm install -g @angular/cli
COPY package*.json ./
RUN npm install
COPY . .
RUN ng build --configuration=production --base-href /ui/

FROM docker.io/library/nginx:stable-alpine AS runner
RUN rm -rf /usr/share/nginx/html/* && mkdir /usr/share/nginx/html/ui/
COPY --from=builder /app/dist/lorad-frontend/browser/* /usr/share/nginx/html/ui/
COPY nginx.conf /etc/nginx/conf.d/lorad.conf
EXPOSE 5477

CMD ["nginx", "-g", "daemon off;"]