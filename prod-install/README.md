# /opt on radio.local

Production home for **ДедоРадио** (LoRaD) on this Raspberry Pi. Operator account is `locchan` (sudo, docker, gpio). This file lives in the repo as `prod-install/README.md` and on the Pi as `/opt/README.md`.

Secrets stay in `/opt/radio/lorad/data/config.json` and `/opt/radio/lorad/.env`. Do not copy them here.

```
/opt/
├── pigpio/cgi/          leftover empty tree from an old GPIO install; unused
└── radio/
    ├── control/         host-side speaker, anthem fallback, volume knob
    ├── lorad/           compose stack + bind-mounted container /data
    └── lorad_build/     how images get rebuilt on this Pi
```

Host install from this tree (as root): `prod-install/install.sh`. It copies `/opt/radio`, systemd units, nginx, `/usr/bin` links, and this README to `/opt/README.md`. It does not start Docker and does not overwrite an existing `config.json` / `.env`.

## Why it is split this way

LoRaD itself runs in Docker (backend stream + REST + WebSocket, static UI). The Pi also has a speaker, a rotary knob, and must keep making sound when the container or the upstream radio dies. That hardware path is systemd + shell on the host, not inside the container.

## `/opt/radio/lorad` — the radio server

**What.** Compose project for two images: `lorad` (Python stream + API) and `lorad-front` (web UI).

**Where.**

| Path | Why |
|---|---|
| `docker-compose.yml` | Wires images, ports, restart, SYS_NICE, host `/dev/shm`, and the data bind |
| `.env` | `LORAD_VERSION` (image tag), `CFGFILE_PATH`, and frontend URL pieces |
| `data/` | Bind-mounted to `/data` in `lorad`. Survives image rebuilds |
| `data/config.json` | LoRaD config (features, ports, bitrate, programs, credentials, Immich) |
| `data/stations.json` | Restreamer station id → Icecast URL |
| `data/resources/` | Jingle, fallback anthem, ads, random voice clips |
| `data/neurovoice/` | TTS clips and news digests written by NEURONEWS |

**How.** `lorad` publishes `5475` (MP3 stream), `5476` (REST), and `5478` (WebSocket). `lorad-front` publishes `5477`. Host nginx on `:80` is the public entry and redirects `/` to `/ui/`. The backend container is privileged, binds the host `/dev/shm` (so LoRaD's pin directory is visible on the Pi), uses tmpfs `/tmp`, and reads config from `/data` via `CFGFILE_PATH`.

**Why these ports.** 5475 is what the speaker loop and any remote listener tune. 5476 is the control API. 5478 is `/whatsplaying` and other WebSocket endpoints. 5477 is the UI container itself.

Nginx locations:

| Path | Upstream |
|---|---|
| `/ui/` | `127.0.0.1:5477/ui/` |
| `/radio` | `127.0.0.1:5475/` (stream) |
| `/radio/api/` | `127.0.0.1:5476/` |
| `/radio/ws/` | `127.0.0.1:5478/` (long read timeout) |

`data/resources/ads` and `data/resources/random_voices` are world-writable so clips can be dropped in without a root shell. `FALLBACK_TRACK_DIR` is `data/resources/fallback_tracks` (`gimn.mp3`) — FileStreamer plays this if a download fails; the host `gimn` service plays the same file (via a copy in `/dev/shm/lorad/pinned`) if the HTTP stream is gone.

Stations in `stations.json`:

| id | name | url |
|---|---|---|
| `belarus` | Радио "Беларусь" | `https://media2.datacenter.by/stream/belarussputnik/stream` |
| `kultura` | Радио "Культура" | `https://media2.datacenter.by/stream/kultura/stream` |

`RESTREAMER.STATION` in config picks the default (`kultura`). Players can still be switched at runtime via the API.

## `/opt/radio/control` — the speaker

**What.** Keep the room playing LoRaD, and keep *something* playing when LoRaD is not.

**Where / how.**

| File | What it does |
|---|---|
| `radio_player.sh` | Loop: Range-GET `127.0.0.1:5475` and require `Content-Type: audio/mpeg`. Then fill ~32KB of stream into shm, `systemctl stop gimn`, wait until the unit is inactive (~250ms), then `mpg123` from that growing buffer (`chrt` / `-b 1024`). On stall (`--speed-limit 1024 --speed-time 10`) or miss, start `gimn` and retry every 5s |
| `gimn.sh` | Copy `gimn.mp3` into `/dev/shm/lorad/pinned` if needed, then loop `mpg123` with a 3s pause (`chrt` / `-b 1024`) |
| `volume.sh` | `amixer` PCM. Human ±N mapped onto 45–95% ALSA; below 45% snaps to mute |
| `volume_knob.py` | `gpiozero` rotary on BCM 17/27, button 22; calls `volume +1` / `volume -1` |
| `systemd/radio.service` | `ExecStart=/usr/bin/radio_player`, `After=network-online.target`, FIFO 20, restart on failure |
| `systemd/gimn.service` | `ExecStart=/usr/bin/gimn`, same realtime class |
| `systemd/volume.service` | `ExecStart=/opt/radio/control/volume_knob.py` |
| `resources/voland.mp3` | Old leftover clip; not referenced by current scripts |

Host bins (from `install.sh`):

- `/usr/bin/radio_player` → `radio_player.sh`
- `/usr/bin/gimn` → `gimn.sh`
- `/usr/bin/volume` → `volume.sh`

Units in `/etc/systemd/system` are symlinks into this `systemd/` folder (`radio`, `gimn`, and `volume` when GPIO is enabled).

**Why a host player.** The container only serves HTTP. `mpg123` + ALSA + GPIO have to sit on the Pi. The anthem exists so a backend restart or a dead upstream is not silence. The prebuffer + wait after `stop gimn` exists so ALSA is free and mpg123 is not started on an empty pipe.

## `/opt/radio/lorad_build` — images

**What.** `build-upgrade.sh` rebuilds `local/lorad-arm:${LORAD_VERSION}` and `local/lorad-front-arm:${LORAD_VERSION}` on this ARM box.

**How.** Sources `config` (symlink to `/opt/radio/lorad/.env`), stops `radio` and the two containers, clones `https://github.com/locchan/lorad` at branch `${LORAD_VERSION}`, builds `Dockerfile_upgrade_arm` and `frontend/Dockerfile` if those tags are missing, deletes the clone, starts `radio` again.

**Why it does not `compose up`.** It only ensures images exist and brings the speaker back. Starting/recreating containers is a separate compose step if the tag in `.env` changed.

## `/opt/pigpio`

Empty `cgi/` directory from the packaged pigpio install. `pigpiod` is not used; the knob talks GPIO through `gpiozero`. Safe to ignore.

## Everyday commands

```bash
cd /opt/radio/lorad && docker compose ps
docker logs -f lorad

systemctl status radio gimn volume
journalctl -u radio -f

# rebuild images for the tag in .env (does not compose up)
sudo /opt/radio/lorad_build/build-upgrade.sh
```
