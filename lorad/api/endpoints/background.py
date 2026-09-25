from lorad.api.utils.decorators import lrd_api_endp, lrd_auth
from lorad.api.utils.immich import pick_background_jpeg
import lorad.common.utils.globs as globs
from lorad.common.utils.misc import read_config

ENDP_PATH = "/background"
LOGIN_REQUIRED = True
DOCSTRING = {
    "GET": "Random JPEG of an Immich asset tagged with enough configured people. Admin only. Carries X-Background-Date (YYYY-MM-DD) when Immich knows when the photo was taken. Disabled feature → 501; missing Immich config → 404."
}
OPTIONAL_FIELDS = {}


@lrd_auth(globs.CAP_ADMIN)
@lrd_api_endp
def impl_GET(headers, data=None):
    if globs.FEAT_IMMICH_BACKGROUNDS not in read_config().get("ENABLED_FEATURES", []):
        return (501, {"error": "IMMICH_BACKGROUNDS feature is disabled."})
    picked = pick_background_jpeg()
    if not picked:
        return {"rc": 404, "data": {"error": "No background available."}}
    jpeg, date = picked
    result = {
        "rc": 200,
        "data": jpeg,
        "content-type": "image/jpeg",
        "cache-control": "private, max-age=3600",
    }
    # Undated assets simply come back without the header
    if date:
        result["headers"] = {"X-Background-Date": date}
    return result
