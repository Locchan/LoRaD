from lorad.audio.file_sources.yandex.YaMu import YaMu
from lorad.audio.server import AudioStream
from lorad.audio.sources.FileStreamer import FileStreamer
from lorad.audio.sources.RadReStreamer import RadReStreamer

FEATURE_FLAGS = []
TEMPDIR = ""

LOCALE = ""

CURRENT_DATA_STREAMER : AudioStream = None

FILESTREAMER : FileStreamer = None
YANDEX_OBJ : YaMu = None

RESTREAMER : RadReStreamer = None

PLAYERS = []
CURRENT_PLAYER_NAME = ""

FLG_DEBUG = "DEBUG"
FLG_NO_DOWNLOADING = "NO_DOWNLOADING"

FEAT_FILESTREAMER = "FILESTREAMER"
FEAT_FILESTREAMER_YANDEX = "FILESTREAMER:YANDEX"
FEAT_RESTREAMER = "RESTREAMER"
FEAT_NEURONEWS = "NEURONEWS"
FEAT_REST = "REST"

LOGIN_NO_SUCH_USER = 0
LOGIN_SUCCESS = 1
LOGIN_INCORRECT_PASSWORD = 2

CAP_IMBA = "ALL"
CAP_ADMIN = "ADMIN"
CAP_BASIC_USER = "BU"

RESTREAMER_DEFAULT_FORMAT = "mp3"
