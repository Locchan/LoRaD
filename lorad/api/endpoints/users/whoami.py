from lorad.api.utils.decorators import lrd_api_endp, lrd_auth
from lorad.api.utils.misc import get_username_from_headers
import lorad.common.utils.globs as globs

ENDP_PATH = "/user/whoami"
LOGIN_REQUIRED = True
DOCSTRING = {"GET": "Returns the username of the logged in user."}
RESULT_EXAMPLE = {"GET": "{'whoami': 'admin'}"}

@lrd_auth(globs.CAP_BASIC_USER)
@lrd_api_endp
def impl_GET(headers):
    return {"whoami": get_username_from_headers(headers)}
