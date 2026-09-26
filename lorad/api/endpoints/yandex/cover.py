from lorad.api.utils.decorators import lrd_api_endp, lrd_auth, lrd_feat_req
from lorad.api.utils.misc import get_current_player
import lorad.common.utils.globs as globs

ENDP_PATH = "/yandex/cover"
LOGIN_REQUIRED = True
DOCSTRING = {
    "GET": "JPEG cover art for the currently playing Yandex track (from cleanable SHM cache). 404 while not ready or when not on a Yandex track."
}
OPTIONAL_FIELDS = {}


@lrd_auth(globs.CAP_BASIC_USER)
@lrd_feat_req(globs.FEAT_FILESTREAMER_YANDEX)
@lrd_api_endp
def impl_GET(headers, data=None):
    player = get_current_player()
    getter = getattr(player, "current_cover_bytes", None) if player is not None else None
    jpeg = getter() if callable(getter) else None
    if not jpeg:
        return (404, {"error": "Cover not ready."})
    return {
        "rc": 200,
        "data": jpeg,
        "content-type": "image/jpeg",
        "cache-control": "private, max-age=60",
    }
