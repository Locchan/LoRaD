from lorad.api.utils.decorators import lrd_api_endp, lrd_auth
import lorad.common.utils.globs as globs
from lorad.common.utils.misc import repr_track

ENDP_PATH = "/yandex/current_track"
LOGIN_REQUIRED = True
DOCSTRING = {"GET": "Returns the current track."}
RESULT_EXAMPLE = "{'track': 'Darude - Sandstorm'}"

@lrd_api_endp
@lrd_auth(globs.CAP_BASIC_USER)
def impl_GET(headers):
    return {"track": repr_track(globs.RADIO_YAMU.radio.current_track)}