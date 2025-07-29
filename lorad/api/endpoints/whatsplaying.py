from lorad.api.utils.decorators import lrd_api_endp, lrd_auth
import lorad.common.utils.globs as globs
from lorad.api.utils.misc import whatsplaying, get_current_player

ENDP_PATH = "/whatsplaying"
LOGIN_REQUIRED = True
DOCSTRING = {"GET": "Returns the currently playing track/program/file/etc."}
RESULT_EXAMPLE = "{'player': 'Radio Player', 'playing': 'Радио \"Культура\"'}"

@lrd_auth(globs.CAP_BASIC_USER)
@lrd_api_endp
def impl_GET(headers):
    return {
        "player_readable": get_current_player().name_readable,
        "player_tech": get_current_player().name_tech,
        "playing": whatsplaying()
    }