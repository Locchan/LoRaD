from lorad.api.utils.decorators import lrd_api_endp, lrd_auth, lrd_feat_req
from lorad.api.utils.misc import get_current_player
import lorad.common.utils.globs as globs

ENDP_PATH = "/yandex/next_track"
LOGIN_REQUIRED = True
DOCSTRING = {"POST": "Skip to the next Yandex track. Starts buffering immediately and returns; does not wait for cutover."}
REQUIRED_FIELDS = {}
OPTIONAL_FIELDS = {}

@lrd_auth(globs.CAP_BASIC_USER)
@lrd_feat_req(globs.FEAT_FILESTREAMER_YANDEX)
@lrd_api_endp
def impl_POST(headers, data):
    player = get_current_player()
    if player is None or not getattr(player, "supports_next_track", lambda: False)():
        return (406, {"error": "Current source cannot skip to the next track."})
    if getattr(player, "_skip_busy", False) or getattr(player, "switching", False):
        return (409, {"error": "A skip is already in progress."})
    ok = player.skip_to_next()
    if not ok:
        return (409, {"error": "Could not skip (busy or buffer failed)."})
    return {"success": True}
