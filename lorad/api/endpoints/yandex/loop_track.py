from lorad.api.utils.decorators import lrd_api_endp, lrd_auth, lrd_feat_req
from lorad.api.utils.misc import get_current_player
import lorad.common.utils.globs as globs

ENDP_PATH = "/yandex/loop_track"
LOGIN_REQUIRED = True
DOCSTRING = {"POST": "Repeat the current Yandex track until skip, station change, or player change. Does not send Yandex skip/finish each loop."}
REQUIRED_FIELDS = {"POST": ["loop"]}
OPTIONAL_FIELDS = {}


@lrd_auth(globs.CAP_BASIC_USER)
@lrd_feat_req(globs.FEAT_FILESTREAMER_YANDEX)
@lrd_api_endp
def impl_POST(headers, data):
    if "loop" not in data or not isinstance(data["loop"], bool):
        return (400, {"error": "'loop' must be a boolean."})
    player = get_current_player()
    if player is None or globs.FILESTREAMER is None or player.name_tech != globs.FILESTREAMER.name_tech:
        return (406, {"error": "Current source cannot loop a Yandex track."})
    if not hasattr(player, "set_looping"):
        return (406, {"error": "Current source cannot loop a Yandex track."})
    looping = player.set_looping(data["loop"])
    return {"success": True, "looping": looping}
