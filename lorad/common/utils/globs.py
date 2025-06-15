from lorad.audio.file_sources.yandex.YaMu import YaMu
from lorad.audio.playback.FileStreamer import FileStreamer
from lorad.audio.playback.RadReStreamer import RadReStreamer

FEATURE_FLAGS = []
TEMPDIR = ""

RADIO_STREAMER : FileStreamer = None
RADIO_YANDEX : YaMu = None

RESTREAMER : RadReStreamer = None

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
