from lorad.api.utils.decorators import lrd_api_endp
from lorad.common.utils.misc import get_version

ENDP_PATH = "/version"
LOGIN_REQUIRED = False
DOCSTRING = DOCSTRING = {"GET": "Returns the backend version."}
RESULT_EXAMPLE = "{'version': 'LoRaD 0.0.1'}"

@lrd_api_endp
def impl_GET(headers):
    version = get_version()
    return {"version": version}
