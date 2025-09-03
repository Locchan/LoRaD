from lorad.api.utils.decorators import lrd_api_endp, lrd_auth
import lorad.common.utils.globs as globs
from lorad.api.utils.misc import get_current_player

ENDP_PATH = "/current_player"
LOGIN_REQUIRED = True
DOCSTRING = {"GET": "Returns the current player (Yandex/Radio/etc.)."}
RESULT_EXAMPLE = {"GET": "{'player': 'player_radio'}"}

@lrd_auth(globs.CAP_BASIC_USER)
@lrd_api_endp
def impl_GET(headers):
    return {"player": get_current_player().name_tech}