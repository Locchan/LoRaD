# Features that can be enabled via config:
- **FILESTREAMER**
- **FILESTREAMER:YANDEX**
- **RESTREAMER**
- **NEURONEWS**
- **API**

# Feature flags available:
- **DEBUG** - debug logging and debug logic
- **NO_DOWNLOADING** - use fallback tracks, don't download stuff

# Configuration:
`config.json` / `config.jsonc` (and `stations.json` / `stations.jsonc`) accept JSON with `//` / `/* */` comments and trailing commas. If both names are given, the exact path is used when it exists; otherwise the other extension is tried. `POST /admin/set_config` rewrites the loaded file as strict JSON.
- **FEATURE_FLAGS**: The list of available feature flags. See above for the available feature flags
- **ENABLED_FEATURES**: The list of enabled features. See above for the available features.
- **DEFAULT_AUDIO_FORMAT**: The format to which all audio will be encoded.
- **STATIONS_FILE_PATH**: Path to the stations file. Default: stations.json or stations.jsonc
- **RESTREAMER**: (RESTREAMER) Radio restreamer configuration. \
Example:\
{"STATION": "default"}
- **REST**: (API) REST API configuration.\
Example:\
{"LISTEN_PORT": 5476,"WS_LISTEN_PORT": 5478,"MAX_DATA_LEN_BYTES": 1024000,"TOKEN_EXPIRATION_MIN": 1440}
- **YAMU_TOKEN**: (FILESTREAMER:YANDEX) Yandex Music token.
- **NAME**: The name of the radio.
- **LOCALE**: Locale (language). See lorad/common/localization/dictionary.py for available locales.
- **MAX_SINGLE_IP_CLIENTS**: Maximum number of clients from a single IP.
- **MAX_CLIENTS**: Maximum listeners on the LISTEN_PORT.
- **BITRATE_KBPS**: The constant bitrate which the we will try to maintain.
- **CHUNK_SIZE_KB**: A size of a single chunk of audio data.
- **LISTEN_PORT**: Radio HTTP port,
- **MYSQL**: MySQL credentials.\
Example:\
{"USERNAME": "","PASSWORD": "","ADDRESS": "","DATABASE": ""}
- **FALLBACK_TRACK_DIR**: Directory with fallback tracks to play if the current file streamer fails to download/get a file to play
- **TEMPDIR**: Legacy setting. Transient media is always written to `/dev/shm/lorad`.
- **DATADIR**: Persistent resources directory. Generated voices, re-encoded audio, and digests use `/dev/shm/lorad` instead.
- **RESDIR**: Resouces directory
- **NEWS_PARSER_PERIOD_MIN**: (NEURONEWS) how often the news get parsed.
- **NEWS_NEURIFIER_PERIOD_MIN**: (NEURONEWS) how often the news get summarized by AI (not all news will do that, see code). 
- **ENABLED_PROGRAMS**: Enabled programs and their configuration.
Example:\
"NewsSmall": {"start_times": [],"jingle_path": "","preparation_needed_mins": ""}
- **OPENAI_API_KEY**: nuff said
- **OPENAI_MODEL**: OpenAI chat model for news summarizer / fake-news / ranking. Default: `gpt-4o-mini`
- **NEWS_TTS_PROVIDER**: News speech provider: `google` (default) or `fish_audio`.
- **GOOGLE_CLOUD_API_USERDATA**: Whole Google API auth JSON. Required when `NEWS_TTS_PROVIDER` is `google`.
- **GOOGLE_TTS_LANGUAGE** / **GOOGLE_TTS_VOICE**: Optional Google voice overrides. Defaults: `ru-RU` / `ru-RU-Standard-B`.
- **FISH_AUDIO_API_KEY**: Fish Audio API key. Required when `NEWS_TTS_PROVIDER` is `fish_audio`.
- **FISH_AUDIO_REFERENCE_ID**: Fish Audio voice model ID from the Voice Library or your custom models.
- **FISH_AUDIO_BASE_URL**: Optional Fish API base URL. Default: `https://api.fish.audio`.
- **FISH_AUDIO_TIMEOUT_SECONDS**: Optional request timeout. Default: `120`.

The Fish integration always sends the `s2.1-pro-free` model header. That model is
currently priced at $0 under Fish Audio's fair-use policy, with no SLA or latency
guarantee; the model is intentionally not configurable to avoid accidental paid use.