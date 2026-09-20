# LoRaD frontend

Static HTML/CSS/JS UI for LoRaD. No build step.

## Pages

- `#/` player
- `#/login` login
- `#/schedule` news schedule

API, WebSocket, and stream URLs are built in `js/config.js` from `domain`, `scheme`, `apiPath`, `radioPath`, and `wsPath`. Docker builds can override the full URLs with `LORAD_API_URL`, `LORAD_RADIO_URL`, and `LORAD_WS_URL`.

## Local preview (no Docker)

API and stream still come from `js/config.js` (defaults: `radio.locchan.dev`). Point them at a running LoRaD, then:

```bash
python3 -m http.server 5477
```

Open `http://localhost:5477/`.

## Local Docker (host API + stream)

Run LoRaD on the host (`5475` stream, `5476` REST, `5478` WebSocket), then:

```bash
./frontend/run-local-docker.sh
```

That rebuilds the image with `http://127.0.0.1:5476`, `http://127.0.0.1:5475`, and `ws://127.0.0.1:5478`, replaces container `lorad-front-local`, and publishes the UI at `http://127.0.0.1:5477/ui/`.

Optional env: `LORAD_API_URL`, `LORAD_RADIO_URL`, `LORAD_WS_URL`, `LORAD_FRONT_PORT`, `LORAD_FRONT_NAME`, `LORAD_FRONT_IMAGE`.

## Docker (other environments)

Development image (keeps `js/config.js` defaults, `radio.locchan.dev`):

```bash
docker build -t lorad-front .
```

Production image (`radio.local`, HTTP, host nginx paths `/radio` and `/radio/api`):

```bash
docker build -t lorad-front --build-arg LORAD_ENV=production .
```

Override any piece:

```bash
docker build -t lorad-front \
  --build-arg LORAD_ENV=production \
  --build-arg LORAD_DOMAIN=radio.local \
  --build-arg LORAD_SCHEME=http \
  --build-arg LORAD_API_PATH=/radio/api \
  --build-arg LORAD_RADIO_PATH=/radio \
  .
```

nginx listens on `5477` and serves the UI at `/ui/`.
