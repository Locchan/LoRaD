from lorad.api.utils.decorators import lrd_api_endp, lrd_auth
import lorad.common.utils.globs as globs
from lorad.api.utils.misc import get_players_names

ENDP_PATH = "/available_players"
LOGIN_REQUIRED = True
DOCSTRING = {"GET": "Returns the available players."}
RESULT_EXAMPLE = "{'player_radio': 'Radio Player', 'player_streaming': 'Streaming player'}"

@lrd_auth(globs.CAP_BASIC_USER)
@lrd_api_endp
def impl_GET(headers):
    return get_players_names()