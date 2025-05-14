from lorad.radio.music.yandex.YaMu import YaMu
from lorad.radio.stream.Streamer import Streamer

FEATURE_FLAGS = []
TEMPDIR = ""

RADIO_STREAMER : Streamer = None
RADIO_YAMU : YaMu = None

FLG_DEBUG = "DEBUG"
FLG_NO_DOWNLOADING = "NO_DOWNLOADING"

FEAT_NEURONEWS = "NEURONEWS"
FEAT_REST = "REST"

LOGIN_NO_SUCH_USER = 0
LOGIN_SUCCESS = 1
LOGIN_INCORRECT_PASSWORD = 2

CAP_IMBA = "ALL"
CAP_ADMIN = "ADMIN"
CAP_BASIC_USER = "BU"