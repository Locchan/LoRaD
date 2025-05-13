from lorad.api.utils.decorators import lrd_api_endp, lrd_auth
from lorad.api.utils.misc import get_username_from_headers
from lorad.common.utils.globs import CAP_BASIC_USER

ENDP_PATH = "/user/whoami"

@lrd_api_endp
@lrd_auth(CAP_BASIC_USER)
def impl_GET(headers):
    return {"whoami": get_username_from_headers(headers)}
