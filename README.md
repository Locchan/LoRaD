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
- **FEATURE_FLAGS**: The list of available feature flags. See above for the available feature flags
- **ENABLED_FEATURES**: The list of enabled features. See above for the available features.
- **DEFAULT_AUDIO_FORMAT**: The format to which all audio will be encoded.
- **RESTREAMER**: (RESTREAMER) Radio restreamer configuration. \
Example:\
{"STATION": "default"}
- **REST**: (API) REST API configuration.\
Example:\
{"LISTEN_PORT": 5476,"MAX_DATA_LEN_BYTES": 1024000,"TOKEN_EXPIRATION_MIN": 1440}
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
- **TEMPDIR**: Temporary directory
- **DATADIR**: Data directory
- **RESDIR**: Resouces directory
- **NEWS_PARSER_PERIOD_MIN**: (NEURONEWS) how often the news get parsed.
- **NEWS_NEURIFIER_PERIOD_MIN**: (NEURONEWS) how often the news get summarized by AI (not all news will do that, see code). 
- **ENABLED_PROGRAMS**: Enabled programs and their configuration.
Example:\
"NewsSmall": {"start_times": [],"jingle_path": "","preparation_needed_mins": ""}
- **OPENAI_API_KEY**: nuff said
- **GOOGLE_CLOUD_API_USERDATA**: Whole google API auth json