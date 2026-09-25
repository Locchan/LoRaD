# Features that can be enabled via config (`ENABLED_FEATURES`):

Exact strings (also in `lorad/common/utils/globs.py`):

- **FILESTREAMER** — file carousel (needs at least one provider)
- **FILESTREAMER:YANDEX** — Yandex Music provider for that carousel
- **RESTREAMER** — live HTTP radio restreamer
- **NEURONEWS** — news parse / TTS / scheduled `NewsSmall`
- **REST** — REST + WebSocket API (older notes call this `API`; the value is `REST`)
- **NEWS_FAKENEWS** — mix two AI-falsified items into the news digest
- **NEWS_ADVERTISEMENTS** — append files from `DATADIR/resources/ads`
- **NEWS_RANDOM_FILES** — append files from `DATADIR/resources/random_voices`
- **IMMICH_BACKGROUNDS** — authenticated Immich-backed UI backgrounds

Yandex needs both `FILESTREAMER` and `FILESTREAMER:YANDEX`.

# Feature flags (`FEATURE_FLAGS`, or top-level `"DEBUG": true`):

- **DEBUG** — debug logging
- **NO_DOWNLOADING** — YaMu skips downloads and plays fallback tracks

# Configuration

`config.json` / `config.jsonc` (and `stations.json` / `stations.jsonc`) accept JSON with `//` / `/* */` comments and trailing commas. Path is env `CFGFILE_PATH`, else `./config.json` or `./config.jsonc`. If a path is given with one extension and missing, the other is tried. `POST /admin/set_config` rewrites the loaded file as strict JSON (comments are not kept).

Stations file (`STATIONS_FILE_PATH`, default `stations.json` / `stations.jsonc`): `{ "<id>": { "name": "...", "url": "http..." } }`.

- **FEATURE_FLAGS**: list of flags (see above). `DEBUG` is also accepted as a top-level boolean.
- **ENABLED_FEATURES**: modules to start (see above).
- **DEFAULT_AUDIO_FORMAT**: codec name passed to ffmpeg (`mp3`).
- **STATIONS_FILE_PATH**: restreamer stations file.
- **RESTREAMER**: `{ "STATION": "<id>" }` — default station id from the stations file.
- **REST**: `{ "LISTEN_PORT": 5476, "WS_LISTEN_PORT": 5478, "MAX_DATA_LEN_BYTES": 1024000, "TOKEN_EXPIRATION_MIN": 1440 }`
- **YAMU_TOKEN**: Yandex Music token (`FILESTREAMER:YANDEX`).
- **NAME**: radio name; also in log lines.
- **LOCALE**: `EN` or `RU` (`lorad/common/localization/dictionary.py`).
- **MAX_SINGLE_IP_CLIENTS**: when total listeners exceed `MAX_CLIENTS`, any IP with more than this many connections is kicked for the process lifetime (default 2).
- **MAX_CLIENTS**: listener cap on `LISTEN_PORT` (default 10). Over the cap, extras get **503**; already-kicked IPs get **302**.
- **BITRATE_KBPS**: CBR the encoder maintains.
- **CHUNK_SIZE_KB**: MP3 chunk size for hub/encoder (`* 1024` bytes).
- **LISTEN_PORT**: stream HTTP port (images: 5475).
- **MYSQL**: `{ "USERNAME", "PASSWORD", "ADDRESS", "DATABASE" }` plus optional `CHARSET`.
- **FALLBACK_TRACK_DIR**: local MP3s if a FileRide fails. Copied into shm (`pinned/fallback`) at boot.
- **TEMPDIR** / **RUNTIME_MEDIA_DIR**: ignored at runtime. Boot always sets both to `/dev/shm/lorad`.
- **DATADIR**: persistent resources (ads, random voices). Copied into shm at boot.
- **RESDIR**: jingles and other static assets. Copied into shm at boot.
- **NEWS_PARSER_PERIOD_MIN**: (`NEURONEWS`) how often news are parsed.
- **NEWS_NEURIFIER_PERIOD_MIN**: (`NEURONEWS`) how often news are summarized.
- **ENABLED_PROGRAMS**: `"NewsSmall": { "start_times": ["HH:MM"], "jingle_path": "", "preparation_needed_mins": 5 }`
- **OPENAI_API_KEY** / **OPENAI_MODEL**: news summarizer / fake-news (default model `gpt-4o-mini`).
- **NEWS_TTS_PROVIDER**: `google` (default) or `fish_audio`.
- **GOOGLE_CLOUD_API_USERDATA**: full GCP service-account JSON. Required for `google`.
- **GOOGLE_TTS_LANGUAGE** / **GOOGLE_TTS_VOICE**: optional. Defaults `ru-RU` / `ru-RU-Standard-B`.
- **FISH_AUDIO_API_KEY** / **FISH_AUDIO_REFERENCE_ID**: required for `fish_audio`.
- **FISH_AUDIO_BASE_URL**: default `https://api.fish.audio`.
- **FISH_AUDIO_TIMEOUT_SECONDS**: default `120`.
- **IMMICH**: `{ "BASE_URL": "", "API_KEY": "", "BACKGROUNDS": { "PERSON_IDS": [], "MIN_PEOPLE": 3 } }`. Connection keys are shared; `BACKGROUNDS` is only for `GET /background` (`IMMICH_BACKGROUNDS`). Secrets are never returned by `/admin/get_config`.

  API key capabilities (Immich **v3.2.2**, [API docs](https://api.immich.app) and server controllers on the `v3.2.2` line). Create the key in Immich Account Settings and enable only:

  | Capability | Why LoRaD needs it |
  |---|---|
  | `asset.read` | `POST /api/search/metadata` with `personIds` |
  | `asset.view` | `GET /api/assets/{id}/thumbnail?size=preview` |
  | `asset.download` | `GET /api/assets/{id}/original` (fallback if preview is missing; a preview/fullsize request can also redirect here) |

  `people.read` is **not** required: person UUIDs are already in `IMMICH.BACKGROUNDS.PERSON_IDS`. Do not grant `all`.

The Fish integration always sends the `s2.1-pro-free` model header. That model is currently priced at $0 under Fish Audio's fair-use policy, with no SLA or latency guarantee; the model is intentionally not configurable to a paid model.

`POST /admin/set_config` may only write `ENABLED_PROGRAMS/NewsSmall/start_times`. Full HTTP API: `API.md`. Frontend: `frontend/README.md`. Backend agent notes: `AGENTS.md`.
