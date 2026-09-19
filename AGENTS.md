# LoRaD (backend)

LoRaD is a self-hosted internet radio: it muxes downloaded tracks and/or live radio into one HTTP MP3 stream, and optionally interrupts that stream with scheduled AI-voiced news. This file is the agent context for the **Python backend only**. Do not use it as guidance for `frontend/` (static HTML/CSS/JS).

## Stack

- Python `>3.10,<4`, packaged with Poetry (`pyproject.toml`, package `lorad`)
- No web framework. Two stdlib HTTP servers:
  - radio stream: `ThreadingHTTPServer` (`lorad/audio/server/AudioStream.py`)
  - REST API: non-threaded `HTTPServer` (`lorad/api/LoRadAPISrv.py`)
- Threads, not asyncio. Fatal failures call `os._exit`
- SQLAlchemy 2.x + PyMySQL (`mapped_column` / `Mapped[...]`)
- ffmpeg on PATH (transcode, re-encode, concat). Required at runtime; Alpine images install it in the install scripts
- Optional: Yandex Music, OpenAI, Google Cloud TTS

Version is `pyproject.toml` plus commit count. Runtime version is `/version` (Docker) via `get_version()`. `getver.sh` prints a human string.

## Layout

```
lorad_main.py                 # process entry; starts threads
lorad/
  common/                     # config, logger, globs, locale, MySQL
  audio/
    server/AudioStream.py     # listener HTTP stream (audio/mpeg)
    sources/                  # players: FileStreamer, RadReStreamer
    sources/utils/Transcoder.py
    file_sources/             # FileRide providers (YaMu)
    programs/                 # scheduled shows (NewsSmall)
    utils/ffmpeg_utils.py     # file re-encode / concat helpers
  api/                        # REST server, endpoints, user/token ORM
tests/api/                    # live HTTP tests against a running API
full_install.sh               # Alpine image: poetry build + /usr/bin/lorad
upgrade_install.sh            # same, force-reinstall wheel
Dockerfile_full / _upgrade    # ports 5475 (stream) and 5476 (API)
```

Ignore `frontend/` and generated/runtime dirs (`data/`, `temp/`, `dist/`).

## Boot

`lorad_main.py`:

1. `SIGTERM`/`SIGINT` → `os._exit(0)`
2. `read_config()` then `init_localization()`
3. `FEATURE_FLAGS` from config; `DEBUG` enables debug logging
4. Bind stream server on `LISTEN_PORT`
5. For each item in `ENABLED_FEATURES`, start the matching threads and register players
6. If `PLAYERS` is empty, exit
7. `start_player` on the first registered player
8. Watchdog: any dead thread → `os._exit(1)`

Thread names you will see: `HTTPServer`, `Streamer`, `ReStreamer`, `NewsParser`, `Neuro`, `ProgramMgr`, `API`, plus per-listener `WRK#N`, `Transcoder`, `PrgRunner`/`PrgPrep`, `SW_Locker`.

Import order matters. `read_config()` / `get_logger()` run at module import in many files. Config must exist before those imports. `lorad_main.py` loads config before importing `AudioStream` / `FileStreamer` / `YaMu` for that reason.

## Config

JSON file. Path is `CFGFILE_PATH` env, else `./config.json`. First successful `read_config()` is cached in `lorad.common.utils.misc.CONFIG`. `write_config()` dumps JSON and reloads. `read_config(..., reload=True)` forces a reread.

Stations for the restreamer are a second JSON (`STATIONS_FILE_PATH`, default `./stations.json`): `{ "<id>": { "name": "...", "url": "http..." } }`.

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
| `MAX_SINGLE_IP_CLIENTS` | documented; stream kick logic currently uses `>2` connections per IP |
| `TEMPDIR` / `DATADIR` / `RESDIR` | downloads, news audio, jingles |
| `FALLBACK_TRACK_DIR` | local MP3s if a FileRide fails |
| `MYSQL` | `{USERNAME,PASSWORD,ADDRESS,DATABASE}` plus optional `CHARSET` |
| `REST` | `{LISTEN_PORT, MAX_DATA_LEN_BYTES, TOKEN_EXPIRATION_MIN}` |
| `RESTREAMER.STATION` | default station id |
| `YAMU_TOKEN` | Yandex Music |
| `OPENAI_API_KEY` | news summarizer / fake-news |
| `OPENAI_MODEL` | OpenAI chat model (default `gpt-4o-mini`) |
| `GOOGLE_CLOUD_API_USERDATA` | full GCP service-account JSON for TTS |
| `NEWS_PARSER_PERIOD_MIN` / `NEWS_NEURIFIER_PERIOD_MIN` | news loops |
| `ENABLED_PROGRAMS` | `{ "NewsSmall": { start_times, jingle_path, preparation_needed_mins } }` |

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
| `FEAT_REST` | `REST` | API server (README also calls this `API`) |
| `FEAT_FAKE_NEWS` | `NEWS_FAKENEWS` | mix two AI-falsified items into the digest |
| `FEAT_NEWS_ADS` | `NEWS_ADVERTISEMENTS` | append files from `DATADIR/resources/ads` |
| `FEAT_NEWS_RANDOM_FILE` | `NEWS_RANDOM_FILES` | append files from `DATADIR/resources/random_voices` |

**Flags** (`FEATURE_FLAGS`): `DEBUG` (also accepted as top-level `"DEBUG": true`), `NO_DOWNLOADING` (YaMu skips downloads → fallback).

Yandex requires both `FILESTREAMER` and `FILESTREAMER:YANDEX`. FileStreamer with no providers logs an error and does not register a player.

## Process-wide state

`lorad/common/utils/globs.py` is the shared mutable process state: current streamer, players, Yandex object, locale, `SWITCH_LOCK`, station cache, capability strings. Players subclass `GenericPlayer` (`lorad/audio/sources/GenericPlayer.py`): `name_tech`, `name_readable`, `currently_playing`, `start()` / `stop()`, `list_sources()`, `current_source()`, `switch_source(id)`. `switch_players(name, start=True)` is only stop-old / flush-buffer / start-new. Station changes go through the current player's `switch_source`.

Known `name_tech` values: `player_streaming` (`FileStreamer`), `player_radio` (`RadReStreamer`). First registered player becomes the default.

`SWITCH_LOCK` blocks station/player switches (API returns 406). `forbid_switching(seconds)` starts `SW_Locker`. Programs call it for the duration of an unswitcheable track.

## Audio pipeline

```
FileRide / live HTTP  →  Transcoder (ffmpeg stdin/stdout)  →  AudioStream.current_data  →  listeners
```

`AudioStream` is a long-lived `GET /` that sends `audio/mpeg`. Other paths 404. `X-Real-IP` is treated as the client IP when proxied. New listeners get a burst of whatever is already in `current_data`; after that they take the newest chunk. `AudioStream.add_data` keeps a one-chunk deque (pop left, append). `track_ended` / full-buffer rewrite signals a new track. `player_switch` is set during player changes.

Over `MAX_CLIENTS`, any IP with more than two connections is added to `kick_list`. Kicked IPs get a 302 to a YouTube URL. IPs in `kick_list` stay kicked for the process lifetime.

`Transcoder` runs ffmpeg: `-i pipe:0` → MP3 CBR `BITRATE_KBPS` @ 44100. First output is a burst (`>= 2` chunks) so browsers do not stall on switch. `get_transcoded_chunk()` returns `globs.END_OF_TRANSCODED_DATA` (`b'EOTD'`) when input is exhausted. Set `no_more_data = True` after the last source bytes.

`FileStreamer.carousel` loops: `get_current_track()` → `serve_file()` → `next_track()`, rotating providers. On any exception it plays `FALLBACK_TRACK_DIR` (empty dir is fatal). `serve_file` is single-flight (`self.free`). It can pause feeding ffmpeg when there are no listeners (`only_if_listeners_there=True`). FileStreamer is hardcoded to source MP3.

`RadReStreamer.standby` waits until `running`, then preflights the station URL for `Content-Type` / Icecast bitrate and streams through `Transcoder`. Network errors retry with backoff (cap 15s). `current_station` is a stations-file id.

`FileStreamer.chunk_size_bytes` is `CHUNK_SIZE_KB * 102` (not 1024). Transcoder uses `* 1024`. Do not "fix" one without checking pacing.

## File sources

`FileRide` (`lorad/audio/file_sources/FileRide.py`) is the provider interface:

- `initialize()` — set `self.initialized = True`
- `get_current_track()` → `(display_name, filepath)` or invalid (carousel falls back)
- `next_track()` — advance, download, set current

`YaMu` is the only provider. It wraps `yandex_music.Client` + `Radio` (Rotor). Tracks download into `TEMPDIR` as `yandex_<md5>.mp3`. Default station is `user:onyourwave`. Station switches are `FileStreamer.switch_source(station_id)` (stop, `radio.start_radio`, start).

To add a provider: subclass `FileRide`, construct it in `lorad_main.py` when its feature is on, append to `carousel_providers`.

## Programs (scheduled shows)

Enabled only with `NEURONEWS`. `AVAILABLE_PROGRAMS` in `program_mgr.py` is the class registry. Config key = class `name`. Scheduler ticks every 20s and only runs if `AudioStream.connected_clients > 0`.

`GenericPrg` contract:

1. `prepare_program` → `_prepare_program_impl()` must return `{track_name: filepath, ...}` (or fail)
2. At start time, `start_program` stops the current player, plays each file via `FileStreamer.serve_file(..., unswitcheable=True)`, then restores the previous player

`NewsPrgS` (`name = "NewsSmall"`, pretty `"Panorama"`): fetch latest news, TTS any missing `DATADIR/neurovoice/<id>.mp3`, re-encode to stream bitrate, optional ads/random files, concat after the jingle (`RESDIR` + config `jingle_path`), write `DATADIR/neurovoice/digests/news_digest_*.mp3`, mark news used, delete voice/digest files older than 24h.

News pipeline:

1. `parse_news` — sources → `News.add_news` (unique on source+title+date)
2. `neurify_news` — OpenAI (`OPENAI_MODEL`, default `gpt-4o-mini`, radio-announcer prompt) fills `body_prepared`. Summarizer uses `https://openai-proxy.locchan.dev`
3. `voice_news` — Google Cloud TTS `ru-RU-Standard-B` → MP3

`MdzSrc` is the only source. `GenericSource.parse_news()` → `list[News]`. To add a source: subclass, implement `parse_news`, append an instance in `parse_news()`'s `sources` list. To add a program: subclass `GenericPrg`, set class `name`, append the class to `AVAILABLE_PROGRAMS`, add an `ENABLED_PROGRAMS` block.

SQLAlchemy `News.body_prepared is None` filters in `orm/News.py` are Python `is`, not SQL NULL. If you touch those queries, use `.is_(None)` / `.is_not(None)`.

## REST API

Started by `start_api_server()` on `REST.LISTEN_PORT` (images: 5476). **Not multi-threaded.** Keep handlers short; do not block on downloads or ffmpeg from an endpoint.

Exact path match only (no query strings, no trailing slash). Methods: GET and POST. POST body is JSON; over `MAX_DATA_LEN_BYTES` → 413; bad JSON → 400.

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
- Return `(status, payload)`, a payload dict (implies 200), a pre-shaped `{rc, data, content-type?}`, or a string
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

`BU`: `GET /whatsplaying`, `/current_player`, `/available_players`, `/locale`, `/enabled_features`, `/user/whoami`, Yandex/radio station GETs (feature-gated).

`ADMIN`: `POST /user/register`, `/user/remove`, `/switch_player`, `/yandex/switch_station`, `/radio/switch_station`, `/admin/get_config`, `/admin/set_config`. Register: username ≥ 3, password ≥ 8.

`/whatsplaying` on the file player also returns Yandex `station_tech` / `station_readable` (special-case `user:onyourwave` → `"Моя волна"`).

`/switch_player` is feature-gated on `RESTREAMER` even though it switches among all registered players. After a successful player or station switch, switching is locked for 10 seconds.

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

Images are Alpine Python 3.12. `full_install.sh` / `upgrade_install.sh` build the Poetry wheel, install it, copy `lorad_main.py` to `/usr/bin/lorad`, write `/version`, set timezone `Europe/Minsk`. `requests` is imported by the restreamer but is not a direct Poetry dependency; if you add import-time use of a new third-party lib, put it in `pyproject.toml`.

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

- Config and logger execute at import. Instantiating `MySQL`, `AudioStream`, or API classes in a vacuum needs a real `config.json`
- API path matching is literal. `/foo` ≠ `/foo/`
- `lrd_auth` reads `headers._headers` (stdlib private). Pass the real request headers object, not a plain dict, unless you change the decorator
- `FileStreamer.cleanup` does not delete downloaded tracks (the `os.remove` is commented out)
- `NewsPrgS.add_ads` / `add_random_files` assign a new list that `_reencode_news` does not always pass to `ffmpeg_concatenate` — if you touch digest assembly, make the file list consistent
- `lorad/audio/file_sources/yandex/Radio.py` and `RadReStreamer` import `get_logger` / `read_config` from odd places; prefer `lorad.common.utils.*` in new code
- Watchdog uses `athread.is_alive` (method, always truthy) rather than `is_alive()`. Do not rely on it to detect dead threads until that is fixed
- `MAX_SINGLE_IP_CLIENTS` is not what the kick list uses
