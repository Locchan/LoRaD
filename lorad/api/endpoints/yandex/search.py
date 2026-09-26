from lorad.api.utils.decorators import lrd_api_endp, lrd_auth, lrd_feat_req
import lorad.common.utils.globs as globs
from lorad.common.utils.logger import get_logger

ENDP_PATH = "/yandex/search"
LOGIN_REQUIRED = True
DOCSTRING = {"GET": "Search Yandex Music tracks. Pass ?q=. Returns up to 10 hits. Admin only."}
REQUIRED_FIELDS = {"GET": ["q"]}
OPTIONAL_FIELDS = {}
RESULT_EXAMPLE = {"GET": "{'tracks': [{'id': '123:456', 'title': '...', 'artist': '...'}]}"}

logger = get_logger()


@lrd_auth(globs.CAP_ADMIN)
@lrd_feat_req(globs.FEAT_FILESTREAMER_YANDEX)
@lrd_api_endp
def impl_GET(headers, data=None):
    data = data or {}
    query = str(data.get("q", "")).strip()
    if not query:
        return (400, {"error": "'q' must be a non-empty string."})
    yamu = globs.YANDEX_OBJ
    if yamu is None:
        return (406, {"error": "Yandex is not available."})
    try:
        tracks = yamu.search_tracks(query, limit=10)
    except Exception as e:
        logger.warning(f"Yandex search failed: {e.__class__.__name__}: {e}")
        return (502, {"error": "Yandex search failed."})
    return {"tracks": tracks}
