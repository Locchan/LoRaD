FROM node:22-alpine

WORKDIR /app

RUN npm install -g @angular/cli
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

CMD ["ng", "serve", "--host", "0.0.0.0", "--port", "5477"]

EXPOSE 5477