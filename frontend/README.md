# LoRaD frontend

Static HTML/CSS/JS UI for LoRaD. No build step.

## Pages

- `#/` player
- `#/login` login
- `#/schedule` news schedule

API and stream URLs are built in `js/config.js` from `domain`, `scheme`, `apiPath`, and `radioPath`.

## Local preview

```bash
python3 -m http.server 5477
```

Open `http://localhost:5477/`. Production nginx serves the same files under `/ui/`.

## Docker

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
