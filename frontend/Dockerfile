FROM docker.io/library/node:22-alpine AS builder

WORKDIR /app
RUN npm install -g @angular/cli
COPY package*.json ./
RUN npm install
COPY . .

ARG API_URL=127.0.0.1:5476
ARG TITLE=LoRaD
ARG AUTOPLAY=true
ARG BG_IMG=https://upload.wikimedia.org/wikipedia/commons/d/dd/I_G%C4%B1yaseddin_Keyh%C3%BCsrev_Meret_%C3%96wezov_Antalya.jpg

# Create environment file with AUTOPLAY value
RUN echo "export const environment = {production: true, apiUrl: '${API_URL}', autoplay: ${AUTOPLAY}, radioTitle: '${TITLE}', backgroundImage: '${BG_IMG}'};" > src/environments/environment.prod.ts

RUN ng build --configuration=production --base-href /ui/

FROM docker.io/library/nginx:stable-alpine AS runner
RUN rm -rf /usr/share/nginx/html/* && mkdir /usr/share/nginx/html/ui/
COPY --from=builder /app/dist/lorad-frontend/browser/* /usr/share/nginx/html/ui/
COPY nginx.conf /etc/nginx/conf.d/lorad.conf
EXPOSE 5477

CMD ["nginx", "-g", "daemon off;"]
