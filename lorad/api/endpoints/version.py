from lorad.api.utils.decorators import lrd_api_endp
from lorad.common.utils.misc import get_version

ENDP_PATH = "/version"

@lrd_api_endp
def impl_GET(headers):
    version = get_version()
    return {"version": version}
