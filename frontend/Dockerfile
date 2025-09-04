FROM docker.io/library/node:22-alpine AS builder

# Accept AUTOPLAY build argument
ARG AUTOPLAY=true

WORKDIR /app
RUN npm install -g @angular/cli
COPY package*.json ./
RUN npm install
COPY . .

# Create environment file with AUTOPLAY value
RUN echo "export const environment = { production: true, apiUrl: 'https://radio.locchan.dev/lorad/api', autoplay: ${AUTOPLAY} };" > src/environments/environment.prod.ts

RUN ng build --configuration=production --base-href /ui/

FROM docker.io/library/nginx:stable-alpine AS runner
RUN rm -rf /usr/share/nginx/html/* && mkdir /usr/share/nginx/html/ui/
COPY --from=builder /app/dist/lorad-frontend/browser/* /usr/share/nginx/html/ui/
COPY nginx.conf /etc/nginx/conf.d/lorad.conf
EXPOSE 5477

CMD ["nginx", "-g", "daemon off;"]