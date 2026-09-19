# LoRaD frontend

Static HTML/CSS/JS UI for LoRaD. No build step.

## Pages

- `#/` player
- `#/login` login
- `#/schedule` news schedule

API and stream URLs live in `js/config.js`.

## Local preview

```bash
python3 -m http.server 5477
```

Open `http://localhost:5477/`. Production nginx serves the same files under `/ui/`.

## Docker

```bash
docker build -t lorad-front .
```

nginx listens on `5477` and serves the UI at `/ui/`.
