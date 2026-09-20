from lorad.api.utils.decorators import lrd_api_endp, lrd_auth, lrd_feat_req
from lorad.api.utils.misc import get_current_player
import lorad.common.utils.globs as globs

ENDP_PATH = "/yandex/like_track"
LOGIN_REQUIRED = True
DOCSTRING = {"POST": "Set the liked status of the currently playing Yandex track."}
REQUIRED_FIELDS = {"POST": ["liked"]}
OPTIONAL_FIELDS = {}


@lrd_auth(globs.CAP_BASIC_USER)
@lrd_feat_req(globs.FEAT_FILESTREAMER_YANDEX)
@lrd_api_endp
def impl_POST(headers, data):
    if "liked" not in data or not isinstance(data["liked"], bool):
        return (400, {"error": "'liked' must be a boolean."})
    player = get_current_player()
    if player is None or not getattr(player, "supports_liking", lambda: False)():
        return (406, {"error": "Current source is not a Yandex track."})
    liked = player.set_current_track_liked(data["liked"])
    return {"success": True, "liked": liked}
