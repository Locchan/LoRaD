from lorad.api.utils.decorators import lrd_api_endp, lrd_auth, lrd_feat_req, lrd_validate
from lorad.api.utils.misc import get_current_player, forbid_switching
import lorad.common.utils.globs as globs

ENDP_PATH = "/yandex/play_track"
LOGIN_REQUIRED = True
DOCSTRING = {
    "POST": "Clear the custom playlist and start playing a Yandex track by id. Returns once the job is accepted; download/cutover continues in the background. Admin only."
}
REQUIRED_FIELDS = {"POST": ["track_id"]}
OPTIONAL_FIELDS = {}


def validate(headers, data):
    if "track_id" not in data or str(data.get("track_id", "")).strip() == "":
        return "This method requires 'track_id' to be specified."
    player = get_current_player()
    if player is None or globs.FILESTREAMER is None or player.name_tech != globs.FILESTREAMER.name_tech:
        return {"rc": 406, "data": {"message": "Yandex is not the current player."}}
    if globs.SWITCH_LOCK or getattr(player, "switching", False) or getattr(player, "_skip_busy", False):
        return {"rc": 406, "data": {"message": "Cannot switch right now. Try later."}}
    return


@lrd_auth(globs.CAP_ADMIN)
@lrd_feat_req(globs.FEAT_FILESTREAMER_YANDEX)
@lrd_validate(validate)
@lrd_api_endp
def impl_POST(headers, data):
    player = get_current_player()
    track_id = str(data["track_id"]).strip()
    ok = player.play_track_id(track_id)
    if not ok:
        return (409, {"error": "Could not play track (busy)."})
    forbid_switching(10)
    return {"success": True}
