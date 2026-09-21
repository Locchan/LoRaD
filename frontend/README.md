# LoRaD frontend

Static HTML/CSS/JS UI. No build step. Hash routes, three views in `index.html`.

## Pages

- `#/login` — username ≥ 3, password ≥ 8 (`POST /user/auth`)
- `#/` — player (stream + WebSocket)
- `#/schedule` — news start times (`GET`/`POST /admin/get_config` and `/admin/set_config` for `ENABLED_PROGRAMS/NewsSmall/start_times`)

Auth is `localStorage` (`username` + `authToken`). REST uses `Authorization: <username>, <token>`. A 401 dispatches `lorad:unauthorized` and returns to login.

## Player behavior

- Stream URL is `radioUrl` plus a cache-busting `?t=`. Volume is local (`<audio>` + `localStorage`); it is never disabled by backend state.
- `/whatsplaying` (WebSocket on `wsUrl`) is the live source of track, skip, like, playhead, and `can_switch`. A change in `can_switch` greys out player/station dropdowns, play/pause, skip, like, and refresh. Volume stays usable.
- Station `<select>` values are technical ids; labels are readable names. `user:onyourwave` is always shown as **Моя волна**. Radio stations come from `/radio/*`; file/Yandex from `/yandex/*`. Radio `whatsplaying` frames do not carry station fields — current radio id is loaded from `/radio/current_station`.
- Playhead: the UI ticks locally and resyncs if the server `position_s` drifts by more than 2 seconds.
- Live-stream buffer: if the browser holds more than `maxBufferKb` ahead of the playhead, the UI seeks to the edge (or reconnects if the stream is not seekable).

## Config (`js/config.js`)

Built from `domain`, `scheme`, `apiPath`, `radioPath`, `wsPath`, or full-URL overrides. Docker/`apply-config.sh` rewrites those string literals.

| Key | Role |
|---|---|
| `apiUrl` / `radioUrl` / `wsUrl` | REST, MP3 stream, WebSocket base |
| `autoplay` | start `<audio>` after init (default `false`) |
| `radioTitle` | `document.title` only |
| `maxBufferKb` / `streamBitrateKbps` | live-buffer watchdog |

## Local preview (no Docker)

Point `js/config.js` at a running LoRaD, then:

```bash
python3 -m http.server 5477
```

Open `http://localhost:5477/`.

## Local Docker (host API + stream)

Run LoRaD on the host (`5475` stream, `5476` REST, `5478` WebSocket), then:

```bash
./frontend/run-local-docker.sh
```

Rebuilds with `http://127.0.0.1:5476`, `http://127.0.0.1:5475`, `ws://127.0.0.1:5478`, replaces container `lorad-front-local`, UI at `http://127.0.0.1:5477/ui/`.

Optional env: `LORAD_API_URL`, `LORAD_RADIO_URL`, `LORAD_WS_URL`, `LORAD_FRONT_PORT`, `LORAD_FRONT_NAME`, `LORAD_FRONT_IMAGE`.

## Docker (other environments)

Development image (keeps `js/config.js` defaults, `radio.locchan.dev`):

```bash
docker build -t lorad-front .
```

Production image (`radio.local`, HTTP, host nginx paths `/radio`, `/radio/api`, `/radio/ws`):

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
  --build-arg LORAD_WS_PATH=/radio/ws \
  .
```

Full URL overrides: `LORAD_API_URL`, `LORAD_RADIO_URL`, `LORAD_WS_URL`.

nginx listens on `5477` and serves the UI at `/ui/`.
