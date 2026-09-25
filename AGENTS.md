# LoRaD (backend)

LoRaD is a self-hosted internet radio: it muxes downloaded tracks and/or live radio into one HTTP MP3 stream, and optionally interrupts that stream with scheduled AI-voiced news. This file is the agent context for the **Python backend only**. Do not use it as guidance for `frontend/` (static HTML/CSS/JS).

## Stack

- Python `>3.10,<3.14`, packaged with Poetry (`pyproject.toml`, package `lorad`). Images use 3.12. The locked `openai`/`pydantic-core` stack has no 3.14 wheels.
- No web framework. Three stdlib HTTP servers:
  - radio stream: `ThreadingHTTPServer` (`lorad/audio/server/AudioStream.py`)
  - REST API: non-threaded `HTTPServer` (`lorad/api/LoRadAPISrv.py`)
  - WebSocket API: threaded `HTTPServer` on `REST.WS_LISTEN_PORT`
- Threads, not asyncio. Fatal failures call `os._exit`
- SQLAlchemy 2.x + PyMySQL (`mapped_column` / `Mapped[...]`)
- ffmpeg on PATH (transcode, re-encode, concat). Required at runtime; Alpine images install it in the install scripts
- Optional: Yandex Music, OpenAI, Google Cloud TTS, Fish Audio TTS

Version is `pyproject.toml` plus commit count. Runtime version is `/version` (Docker) via `get_version()`. `getver.sh` prints a human string.

## Layout

```
lorad_main.py                 # process entry; starts threads
lorad/
  common/                     # config, logger, globs, locale, MySQL, shm
  audio/
    hub.py                    # exclusive PCM bus + long-lived MP3 encoder
    ramfile.py                # RAM double-buffer of current/next MP3
    server/AudioStream.py     # listener HTTP stream (audio/mpeg)
    sources/                  # players: FileStreamer, RadReStreamer
    sources/utils/Transcoder.py  # Decoder (per source) + Encoder (hub)
    file_sources/             # FileRide providers (YaMu)
    programs/                 # scheduled shows (NewsSmall)
    utils/ffmpeg_utils.py     # file re-encode / concat helpers
  api/                        # REST server, endpoints, user/token ORM
tests/api/                    # live HTTP tests against a running API
full_install.sh               # Alpine image: poetry build + /usr/bin/lorad
upgrade_install.sh            # same, force-reinstall wheel
Dockerfile_full / _upgrade    # ports 5475 (stream), 5476 (REST), 5478 (WebSocket)
```

Ignore `frontend/` and generated/runtime dirs (`data/`, `temp/`, `dist/`).

## Boot

`lorad_main.py`:

1. `SIGTERM`/`SIGINT` → `os._exit(0)`
2. `read_config()`, `prepare_shm()` (forces `TEMPDIR`/`RUNTIME_MEDIA_DIR` to `/dev/shm/lorad`), `seed_pinned_assets()`, shm janitor
3. `init_localization()`; `FEATURE_FLAGS` from config; `DEBUG` enables debug logging
4. Bind stream server on `LISTEN_PORT`
5. For each item in `ENABLED_FEATURES`, start the matching threads and register players (Yandex stations cache starts async)
6. If `PLAYERS` is empty, exit
7. `start_player` on the first registered player (`hub.acquire`)
8. Watchdog: any dead thread → `os._exit(1)` (currently broken: see Pitfalls)

Thread names you will see: `HTTPServer`, `Streamer`, `ReStreamer`, `NewsParser`, `Neuro`, `ProgramMgr`, `API`, `API-WS`, `PcmClock`, `Decoder`, `Transcoder`, `ShmJanitor`, `YaStations`, `Prefetch`, `StationSw`, `RamFill`, plus per-listener `WRK#N`, per-WebSocket `WS#N`, `PrgRunner`/`PrgPrep`, `SW_Locker`.

Import order matters. `read_config()` / `get_logger()` run at module import in many files. Config must exist before those imports. `lorad_main.py` loads config before importing `AudioStream` / `FileStreamer` / `YaMu` for that reason.

## Config

JSONC file (`//` and `/* */` comments, trailing commas allowed). Path is `CFGFILE_PATH` env, else `./config.json` or `./config.jsonc` (whichever exists). First successful `read_config()` is cached in `lorad.common.utils.misc.CONFIG`. `write_config()` dumps strict JSON to the file that was loaded (comments are not preserved) and reloads. `read_config(..., reload=True)` forces a reread.

Stations for the restreamer are a second JSONC file (`STATIONS_FILE_PATH`, default `./stations.json` or `./stations.jsonc`): `{ "<id>": { "name": "...", "url": "http..." } }`.

| Key | Role |
|---|---|
| `NAME` | radio name; also appears in log lines |
| `LOCALE` | `EN` or `RU` (`lorad/common/localization/dictionary.py`) |
| `FEATURE_FLAGS` | flags, not features: `DEBUG`, `NO_DOWNLOADING` |
| `ENABLED_FEATURES` | modules to start (see Features) |
| `LISTEN_PORT` | stream port (images: 5475) |
| `BITRATE_KBPS` | target CBR for ffmpeg |
| `CHUNK_SIZE_KB` | transcoder output chunk size |
| `DEFAULT_AUDIO_FORMAT` | output codec name passed to ffmpeg (`mp3`) |
| `MAX_CLIENTS` | stream listener cap (default 10) |
| `MAX_SINGLE_IP_CLIENTS` | over `MAX_CLIENTS`, IPs with more than this many connections are kicked (default 2) |
| `TEMPDIR` / `RUNTIME_MEDIA_DIR` | overwritten at boot to `/dev/shm/lorad` |
| `DATADIR` / `RESDIR` | on-disk assets copied into shm `pinned/` at boot |
| `FALLBACK_TRACK_DIR` | local MP3s if a FileRide fails |
| `MYSQL` | `{USERNAME,PASSWORD,ADDRESS,DATABASE}` plus optional `CHARSET` |
| `REST` | `{LISTEN_PORT, WS_LISTEN_PORT, MAX_DATA_LEN_BYTES, TOKEN_EXPIRATION_MIN}` |
| `RESTREAMER.STATION` | default station id |
| `YAMU_TOKEN` | Yandex Music |
| `OPENAI_API_KEY` | news summarizer / fake-news |
| `OPENAI_MODEL` | OpenAI chat model (default `gpt-4o-mini`) |
| `NEWS_TTS_PROVIDER` | `google` (default) or `fish_audio` |
| `GOOGLE_CLOUD_API_USERDATA` | full GCP service-account JSON for TTS |
| `GOOGLE_TTS_LANGUAGE` / `GOOGLE_TTS_VOICE` | optional Google voice overrides |
| `FISH_AUDIO_API_KEY` / `FISH_AUDIO_REFERENCE_ID` | Fish API key and voice model id |
| `FISH_AUDIO_BASE_URL` / `FISH_AUDIO_TIMEOUT_SECONDS` | optional Fish endpoint/timeout |
| `NEWS_PARSER_PERIOD_MIN` / `NEWS_NEURIFIER_PERIOD_MIN` | news loops |
| `ENABLED_PROGRAMS` | `{ "NewsSmall": { start_times, jingle_path, preparation_needed_mins } }` |
| `IMMICH` | `{BASE_URL, API_KEY, BACKGROUNDS: {PERSON_IDS, MIN_PEOPLE}}`; backgrounds overlap defaults to `3`. API key needs Immich v3.2.2 capabilities `asset.read`, `asset.view`, `asset.download` (see README) |

`EDITABLE_CONFIG_KEYS` in `globs.py` is the allowlist for `POST /admin/set_config`. Today only `ENABLED_PROGRAMS/NewsSmall/start_times`. After that key is written, programs are re-registered.

Do not log or return secrets. Admin get/set already reject keys containing `username`, `password`, `token`, `key`, `private`, `address`, `database`, `auth`.

## Features vs flags

`feature_enabled(name)` is `name in config["ENABLED_FEATURES"]`. Constants live in `lorad/common/utils/globs.py`.

**Features** (`ENABLED_FEATURES`):

| Constant | Value | What starts |
|---|---|---|
| `FEAT_FILESTREAMER` | `FILESTREAMER` | `FileStreamer` carousel (needs at least one provider) |
| `FEAT_FILESTREAMER_YANDEX` | `FILESTREAMER:YANDEX` | `YaMu` provider + `globs.YANDEX_OBJ` |
| `FEAT_RESTREAMER` | `RESTREAMER` | `RadReStreamer` |
| `FEAT_NEURONEWS` | `NEURONEWS` | news parse / neurify / program scheduler |
| `FEAT_REST` | `REST` | REST + WebSocket API |
| `FEAT_FAKE_NEWS` | `NEWS_FAKENEWS` | mix two AI-falsified items into the digest |
| `FEAT_NEWS_ADS` | `NEWS_ADVERTISEMENTS` | append files from `DATADIR/resources/ads` |
| `FEAT_NEWS_RANDOM_FILE` | `NEWS_RANDOM_FILES` | append files from `DATADIR/resources/random_voices` |
| `FEAT_IMMICH_BACKGROUNDS` | `IMMICH_BACKGROUNDS` | enable admin-only Immich backgrounds and warm their cache |

**Flags** (`FEATURE_FLAGS`): `DEBUG` (also accepted as top-level `"DEBUG": true`), `NO_DOWNLOADING` (YaMu skips downloads → fallback).

Yandex requires both `FILESTREAMER` and `FILESTREAMER:YANDEX`. FileStreamer with no providers logs an error and does not register a player.

## Process-wide state

`lorad/common/utils/globs.py` is the shared mutable process state: current streamer, players, Yandex object, locale, `SWITCH_LOCK`, station cache, capability strings. Players subclass `GenericPlayer` (`lorad/audio/sources/GenericPlayer.py`): `name_tech`, `name_readable`, `currently_playing`, `switching`, `start()` / `stop()`, `list_sources()`, `current_source()`, `switch_source(id)`. `switch_players(name, start=True)` stops the old player, `hub.release`s it, then starts the new one and `hub.acquire`s. Station changes go through the current player's `switch_source`.

Known `name_tech` values: `player_streaming` (`FileStreamer`), `player_radio` (`RadReStreamer`). First registered player becomes the default.

`SWITCH_LOCK` blocks station/player switches (API returns 406). `forbid_switching(seconds)` shares one deadline so overlapping timed locks cannot unlock each other early; `seconds <= 0` holds until `allow_switching()`. FileStreamer also sets `player.switching` while a Yandex station prefetch is in flight (same 406). After a successful player/station switch the API locks for 10 seconds. Programs call `forbid_switching()` with no duration at start and `allow_switching()` in `finally`.

## Audio pipeline

```
FileRide / live HTTP
  → AudioHub.begin_source (Decoder ffmpeg: encoded → PCM)
  → PcmClock (realtime PCM, silence when idle)
  → Encoder ffmpeg (PCM → MP3 CBR BITRATE_KBPS)
  → hub.wait_chunk → AudioStream listeners
```

`AudioHub` (`lorad/audio/hub.py`) is exclusive: one owner at a time (`acquire` / `release` / `feed`). `begin_source` reuses the current Decoder when owner, drain flag, and signature `(demuxer, sample_rate, channels)` match; otherwise it restarts ffmpeg and logs why. `release(..., drain=True)` lets the encoder play out remaining PCM; `drain=False` drops it. The encoder is long-lived so listeners always see one continuous MP3 stream.

`AudioStream` is a long-lived `GET /` (and `HEAD /`) that sends `audio/mpeg`. Other paths 404. Query strings are ignored so the UI can cache-bust. `X-Real-IP` is treated as the client IP when proxied. Each worker waits on `hub.wait_chunk` and writes the latest MP3 chunk.

Over `MAX_CLIENTS`, `ddos_protection` adds any IP with more than `MAX_SINGLE_IP_CLIENTS` connections to `kick_list` and returns **503**. Already-kicked IPs get **302** to a YouTube URL. Kicked IPs stay kicked for the process lifetime.

`Decoder` / `Encoder` live in `Transcoder.py`. Decoder: `-f <demuxer> -i pipe:0` → s16le PCM @ 44100 stereo. Encoder: PCM → MP3 CBR `BITRATE_KBPS`. Chunk size is `CHUNK_SIZE_KB * 1024`.

`FileStreamer.carousel` loads tracks into `DoubleBuffer` (`ramfile.py`), feeds the hub, and prefetches the next file ~30s before the end (`Prefetch`). On failure it plays pinned fallback MP3s (empty dir is fatal). Yandex station changes run on `StationSw`: keep the current track playing, load the first new-station track into preload, then skip over. FileStreamer is hardcoded to source MP3.

`RadReStreamer.standby` waits until `running`, then preflights the station URL for `Content-Type` / Icecast bitrate and feeds the hub. `_epoch` increments on `switch_source` so a stale `_stream` loop exits. Network errors retry with backoff (cap 15s). `current_station` is a stations-file id.

## File sources

`FileRide` (`lorad/audio/file_sources/FileRide.py`) is the provider interface:

- `initialize()` — set `self.initialized = True`
- `get_current_track()` → `(display_name, filepath)` or invalid (carousel falls back)
- `next_track()` — advance, download, set current

`YaMu` is the only provider. It wraps `yandex_music.Client` + `Radio` (Rotor). Tracks download into shm (`TEMPDIR`) as `yandex_<md5>.mp3`. Default station is `user:onyourwave`. Station lists always inject synthetic `user:onyourwave` (`Моя волна`) and `user:likes` (`Понравившееся`) at the top in that order, with the rotor stations after them sorted by name, and are pinned to shm (`pinned/yandex_available_stations.json`) at startup via `cache_stations_async()` (`YaStations` thread). `user:likes` shuffles liked tracks locally with no rotor feedback. Station switches are `FileStreamer.switch_source(station_id)` → `YaMu.switch_station` (drop prefetch, `radio.start_radio`, prepare the first new track as next). Looping repeats the current RAM file without Yandex skip/finish.

To add a provider: subclass `FileRide`, construct it in `lorad_main.py` when its feature is on, append to `carousel_providers`.

## Programs (scheduled shows)

Enabled only with `NEURONEWS`. `AVAILABLE_PROGRAMS` in `program_mgr.py` is the class registry. Config key = class `name`. Scheduler ticks every 20s and only runs if `AudioStream.connected_clients > 0`.

`GenericPrg` contract:

1. `prepare_program` → `_prepare_program_impl()` must return `{track_name: filepath, ...}` (or fail)
2. At start time, `start_program` takes an open-ended `SWITCH_LOCK`, `hub.acquire(self)`, plays each prepared file through the hub, then in `finally` `hub.release(self, drain=completed)` and `allow_switching()`, restoring the previous player

`NewsPrgS` (`name = "NewsSmall"`, pretty `"Panorama"`): fetch latest news, TTS any missing `RUNTIME_MEDIA_DIR/neurovoice/<id>.mp3`, re-encode to stream bitrate, optional ads/random files, concat after the jingle (`RESDIR` + config `jingle_path`), write `RUNTIME_MEDIA_DIR/neurovoice/digests/news_digest_*.mp3`, mark news used, and remove intermediate voice files after digest creation.

News pipeline:

1. `parse_news` — sources → `News.add_news` (unique on source+title+date)
2. `neurify_news` — OpenAI (`OPENAI_MODEL`, default `gpt-4o-mini`, radio-announcer prompt) fills `body_prepared`. Summarizer uses `https://openai-proxy.locchan.dev`
3. `voice_news` — provider-neutral `news/tts/service.py` → MP3 in SHM. `NEWS_TTS_PROVIDER=google` uses Google Cloud (`ru-RU-Standard-B` by default); `fish_audio` calls `/v1/tts` with the fixed free model `s2.1-pro-free` and configured `FISH_AUDIO_REFERENCE_ID`

TTS providers implement `TTSProvider.synthesize_mp3(text) -> bytes` under `news/tts/`. Provider modules own API details and map failures to neutral exceptions; the service owns news lookup and atomic SHM writes. Fish's free model is fair-use, has no SLA, and is intentionally not configurable to a paid model.

`MdzSrc` is the only source. `GenericSource.parse_news()` → `list[News]`. To add a source: subclass, implement `parse_news`, append an instance in `parse_news()`'s `sources` list. To add a program: subclass `GenericPrg`, set class `name`, append the class to `AVAILABLE_PROGRAMS`, add an `ENABLED_PROGRAMS` block.

SQLAlchemy `News.body_prepared is None` filters in `orm/News.py` are Python `is`, not SQL NULL. If you touch those queries, use `.is_(None)` / `.is_not(None)`.

## REST API

Started by `start_api_server()` on `REST.LISTEN_PORT` (images: 5476). **Not multi-threaded.** Keep handlers short; do not block on downloads or ffmpeg from an endpoint.

WebSocket endpoints (`@lrd_websocket`) bind a second **threaded** `HTTPServer` on `REST.WS_LISTEN_PORT` (images: 5478). REST GETs of those paths return 426.

Exact path match only (no trailing slash). GET may carry a query string; matching uses the path before `?`. POST body is JSON; over `MAX_DATA_LEN_BYTES` → 413; bad JSON → 400.

### Endpoint module contract

Each module in `lorad/api/endpoints/` (or a package next to it):

```python
ENDP_PATH = "/example"
LOGIN_REQUIRED = True          # docs / OpenAPI only; auth is the decorator
DOCSTRING = {"GET": "...", "POST": "..."}
REQUIRED_FIELDS = {"POST": ["field"]}   # optional
OPTIONAL_FIELDS = {}                    # optional
RESULT_EXAMPLE = {"GET": "{...}"}       # optional, for /apidoc

@lrd_auth(globs.CAP_BASIC_USER)   # if auth needed
@lrd_feat_req(globs.FEAT_RESTREAMER)  # if feature-gated
@lrd_validate(validate)
@lrd_api_endp
def impl_GET(headers):
    return {"ok": True}

@lrd_auth(globs.CAP_ADMIN)
@lrd_validate(validate)
@lrd_api_endp
def impl_POST(headers, data):
    return (201, {"created": True})
```

Rules:

- First argument is always `headers` (`email.message.Message` from the stdlib server)
- GET: `impl_GET(headers)`. POST: `impl_POST(headers, data)` where `data` is a dict
- Return `(status, payload)`, a payload dict (implies 200), a pre-shaped `{rc, data, content-type?, cache-control?, headers?}`, or a string. `headers` is a dict of extra response headers; they are also listed in `Access-Control-Expose-Headers` so the browser can read them cross-origin
- Always register: import the module in the package `__init__` if needed, then append it to `endpoints_to_register` in `lorad/api/endpoints/__init__.py`
- Duplicate `ENDP_PATH`+method is fatal (`os._exit`)
- Decorators **above** `@lrd_api_endp` must return `{rc, data}` (and optional `content-type`). Preferred order, top to bottom: `@lrd_auth` → `@lrd_feat_req` → `@lrd_validate` → `@lrd_api_endp`

`lrd_feat_req` with a list is OR (any listed feature is enough). Missing feature → 405.

### Auth

`Authorization: <username>, <token>` (comma-separated, not Bearer). Tokens are 32 hex chars in `api_token`, TTL `REST.TOKEN_EXPIRATION_MIN`.

Capabilities (`globs`): `BU` basic, `ADMIN` admin, `ALL` bypasses the check. Stored as a comma-separated string on `api_group`. New users land in group `default` with `BU`.

| Code | Meaning |
|---|---|
| 401 | missing/bad/expired token |
| 403 | authenticated, wrong capability |
| 400 | malformed `Authorization` (not exactly two parts) |

`LOGIN_REQUIRED` does not enforce auth. The decorator does. Keep them in sync for `/apidoc` and `/openapi`.

### Endpoints

Unauthenticated: `GET /version`, `GET|POST /apidoc`, `GET /openapi`.

`BU`: WebSocket `GET /whatsplaying` on `WS_LISTEN_PORT`, REST `/current_player`, `/available_players`, `/locale`, `/enabled_features`, `/user/whoami`, Yandex/radio station GETs (feature-gated).

`ADMIN`: `POST /user/register`, `/user/remove`, `/switch_player`, `/yandex/switch_station`, `/radio/switch_station`, `/admin/set_config`. `GET /admin/get_config?key=`. `GET /background` (404 if Immich is not configured; 501 if the feature is off; adds `X-Background-Date` when the asset has a date). `BU`: `POST /yandex/next_track`, `/yandex/like_track`, `/yandex/loop_track`. Register: username ≥ 3, password ≥ 8.

`/whatsplaying` always includes `can_switch` (`not SWITCH_LOCK` and not `player.switching`). Skip sets `FileStreamer.switching` for the same grey-out. A change in `can_switch` is a push. On the file player it also returns Yandex `station_tech` / `station_readable` (synthetic `user:onyourwave` → `"Моя волна"`, `user:likes` → `"Понравившееся"`), plus `liked` while a Yandex track is active, `looping`, and `length_s` / `position_s` for the playhead. Radio has no track and no station fields on this socket; use `/radio/current_station`. `position_s` is excluded from change detection. The server pushes on any other change, and otherwise every `PUSH_PERIOD_S` (30s); the UI counts seconds itself and resyncs past 2s of drift.

Yandex station list always injects those two synthetic ids first (`Моя волна`, then `Понравившееся`) and sorts the rest by name. `user:likes` shuffles `users_likes_tracks` locally with no rotor feedback.

`/switch_player` is feature-gated on `RESTREAMER` even though it switches among all registered players. After a successful player or station switch, switching is locked for 10 seconds. Yandex `switch_station` also 406s while `player.switching`.

## Database

`MySQL.get_session()` lazy-constructs a singleton engine (`pool_pre_ping=True`) and `Base.metadata.create_all` for the ORMs of enabled features:

- `NEURONEWS`: `news`
- `REST`: `api_user`, `api_group`, `api_token`

Always `with MySQL.get_session() as session:`. Handle `IntegrityError` for the news unique constraint. Do not add a second engine.

Passwords are SHA-512 with a hardcoded salt in `hash_password`. Do not change the salt; existing rows would break.

## Localization

`get_loc("KEY")`. Keys must be listed in `DICTIONARY` and present in every `ENABLED_LOCS` entry (`EN`, `RU`). Missing translations log a warning at init. Unknown keys return `UNKNOWN STRING: ...`. Player display names go through this (`PLAYER_NAME_*`). News TTS and OpenAI prompts are Russian regardless of `LOCALE`.

## Logging

`get_logger()` from `lorad/common/utils/logger.py`. File: `/var/log/lorad.log` if writable, else `lorad.log`. Format includes config `NAME`, thread name, file, line. Use `logger.exception(e)` on unexpected errors. Existing code uses `logger.warn`; match nearby style. `setdebug()` flips the default level for new loggers.

## Tests

`tests/api/test_user_mgmt.py` is a live HTTP suite against `localhost:5476`. It expects an existing admin `admin` / `testadmin`. Run only against a disposable instance. Tests are sequential (later tests reuse `TEST_TOKEN`). The "insufficient permissions" cases assert 401; the decorator actually returns 403 — do not "fix" one side without the other.

## Docker / install

Images are Alpine Python 3.12. `full_install.sh` / `upgrade_install.sh` build the Poetry wheel, install it, copy `lorad_main.py` to `/usr/bin/lorad`, write `/version`, set timezone `Europe/Minsk`. Third-party imports used at runtime belong in `pyproject.toml` (`requests` already is).

## Conventions

- Follow existing names and file placement. New API code goes under `lorad/api/endpoints/<area>/`. Shared API helpers go in `lorad/api/utils/misc.py`. Constants and process state go in `globs.py`, not new singleton modules
- Gate optional behavior with `feature_enabled` / `@lrd_feat_req` and a `FEAT_*` constant. Do not silently require Yandex, OpenAI, or GCP
- Do not introduce FastAPI/Flask, asyncio, or a second HTTP stack
- Do not use `any` in TypeScript-style here: this is Python. Type hints are welcome on new code (`Mapped`, `list[News]`) but the repo is not strict-mypy
- Avoid circular imports. Several modules already import across `api` ↔ `audio` (`switch_players`, `forbid_switching`). Prefer importing inside the function when a cycle appears, as `GenericPrg` and `User` already do
- Comments are informal English. Keep them short and say why
- Do not reformat unrelated files. Do not invent config keys without wiring them through `read_config` consumers
- Stream and API both honor `X-Real-IP`. Preserve that if you touch request handling

## Pitfalls

- Config and logger execute at import. Instantiating `MySQL`, `AudioStream`, or API classes in a vacuum needs a real `config.json` or `config.jsonc`
- API path matching is literal. `/foo` ≠ `/foo/`
- `lrd_auth` reads `headers._headers` (stdlib private). Pass the real request headers object, not a plain dict, unless you change the decorator
- The ffmpeg concat list is written into shm and ffmpeg resolves relative `file` entries against that list, so on-disk assets (`RESDIR`, `DATADIR`, `FALLBACK_TRACK_DIR`) are copied into `/dev/shm/lorad/pinned` at boot (`seed_pinned_assets`). The janitor and `unlink_shm` never delete that tree. `local_path()` still resolves the on-disk source (Windows separators included) before the copy.
- `lorad/audio/file_sources/yandex/Radio.py` and `RadReStreamer` import `get_logger` / `read_config` from odd places; prefer `lorad.common.utils.*` in new code
- Watchdog uses `athread.is_alive` (method, always truthy) rather than `is_alive()`. Do not rely on it to detect dead threads until that is fixed
- `lorad_main.py` assigns `config["TEMPDIR"]` after `read_config()`; modules that captured TEMPDIR at import still see the shm path because that assignment happens before FileStreamer/YaMu are imported
