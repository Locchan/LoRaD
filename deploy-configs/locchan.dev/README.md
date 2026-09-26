# /opt/services/lorad on radio.locchan.dev

VPS deploy for **ДедоРадио** behind nginx at `https://radio.locchan.dev`. Operator account is `locchan` (passwordless sudo, docker). This file lives in the repo as `deploy-configs/locchan.dev/README.md` and on the host as `/opt/services/lorad/README.md`.

Secrets stay in `/opt/container_storage/lorad/config.jsonc` and `/opt/services/lorad/envfile.env`. Do not copy them here. Media (`resources/`, digests) stays on the host under `/opt/container_storage/lorad/` and is not part of this tree.

```
/opt/services/lorad/          compose + build/start scripts (this package)
/opt/container_storage/lorad/ bind-mounted container /data
/etc/nginx/sites-enabled/radio
```

Host install from this tree (as `locchan`): `deploy-configs/locchan.dev/install.sh`. It escalates with `sudo -n`, copies scripts to `/opt/services/lorad`, installs the nginx site, seeds empty storage dirs, then `nginx -s reload` and `./restart` in `/opt/services/lorad`. It does not overwrite an existing `envfile.env` / `config.jsonc`, and does not touch `resources/`.

## Why it is split this way

Images are built on the VPS (or pushed to `docker.locchan.dev`) and run on the shared `dockernet` network. Public HTTPS terminates at host nginx; containers publish only on localhost ports. Unlike the Pi (`deploy-configs/dedoradio`), there is no host speaker / GPIO stack.

## `/opt/services/lorad` — scripts + compose

| Path | Why |
|---|---|
| `docker-compose.yaml` | `lorad` + `lorad-front` on `dockernet`, ports 5475/5476/5478/5477, data bind |
| `envfile.env` | `CFGFILE_PATH` (and anything else the containers need at runtime) |
| `config` | registry name + frontend public URL pieces used by build scripts |
| `build` / `build-backend` / `build-frontend` | clone GitHub, build, push to `docker.locchan.dev` |
| `build_upgrade-backend` / `upgrade-backend` | same for `Dockerfile_upgrade` |
| `start` / `stop` / `restart` / `rebuild` / `status` | everyday lifecycle |

**Ports.** Backend: `5475` MP3, `5476` REST, `5478` WebSocket. Frontend: `5477` (UI under `/ui/`).

Nginx locations (fixed for current LoRaD):

| Path | Upstream |
|---|---|
| `/` | `301` → `/ui/` |
| `/ui/` | `127.0.0.1:5477/ui/` |
| `/lorad/api/` | `127.0.0.1:5476/` |
| `/lorad/ws/` | `127.0.0.1:5478/` (HTTP/1.1 upgrade, long read timeout) |
| `/lorad/live` | `127.0.0.1:5475/` (`proxy_buffering off`) |

Frontend image build args (from `config`) must match those paths: `LORAD_DOMAIN=radio.locchan.dev`, `LORAD_SCHEME=https`, `LORAD_API_PATH=/lorad/api`, `LORAD_RADIO_PATH=/lorad/live`, `LORAD_WS_PATH=/lorad/ws`.

TLS is Certbot-managed for `radio.locchan.dev`. The shipped `nginx/radio.conf` keeps the live certificate paths; re-run Certbot if the host is a fresh box.

## `/opt/container_storage/lorad` — data

Bind-mounted to `/data` in `lorad`. Survives image rebuilds.

| Path | Why |
|---|---|
| `config.jsonc` | LoRaD config (`CFGFILE_PATH`); must include `REST.WS_LISTEN_PORT` (5478) |
| `stations.json` | Restreamer station id → URL |
| `resources/` | jingle, fallback, ads, random voices (operator-managed; not in this package) |
| `neurovoice/` | TTS / digests |

## Everyday commands

```bash
cd /opt/services/lorad
./status
./rebuild          # stop, full build+push, start
./upgrade-backend  # stop, upgrade image, start
docker compose ps
docker logs -f lorad
```
