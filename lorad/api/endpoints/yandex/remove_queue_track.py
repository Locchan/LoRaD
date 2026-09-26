from lorad.api.utils.decorators import lrd_api_endp, lrd_auth, lrd_feat_req, lrd_validate
from lorad.api.utils.misc import get_current_player
import lorad.common.utils.globs as globs

ENDP_PATH = "/yandex/remove_queue_track"
LOGIN_REQUIRED = True
DOCSTRING = {
    "POST": "Remove an upcoming track from the custom playlist by list index (same order as whatsplaying custom_queue). Admin only."
}
REQUIRED_FIELDS = {"POST": ["index"]}
OPTIONAL_FIELDS = {}


def validate(headers, data):
    if "index" not in data:
        return "This method requires 'index' to be specified."
    try:
        index = int(data["index"])
    except (TypeError, ValueError):
        return "'index' must be an integer."
    if index < 0:
        return "'index' must be >= 0."
    data["index"] = index
    player = get_current_player()
    if player is None or globs.FILESTREAMER is None or player.name_tech != globs.FILESTREAMER.name_tech:
        return {"rc": 406, "data": {"message": "Yandex is not the current player."}}
    if not getattr(player, "is_playing_custom", lambda: False)():
        return {"rc": 406, "data": {"message": "Custom playlist is not active."}}
    if globs.SWITCH_LOCK or getattr(player, "switching", False) or getattr(player, "_skip_busy", False):
        return {"rc": 406, "data": {"message": "Cannot switch right now. Try later."}}
    return


@lrd_auth(globs.CAP_ADMIN)
@lrd_feat_req(globs.FEAT_FILESTREAMER_YANDEX)
@lrd_validate(validate)
@lrd_api_endp
def impl_POST(headers, data):
    player = get_current_player()
    ok = player.remove_custom_queue_at(data["index"])
    if not ok:
        return (409, {"error": "Could not remove queue track."})
    return {
        "success": True,
        "custom_queue": player.custom_queue_list(),
    }
