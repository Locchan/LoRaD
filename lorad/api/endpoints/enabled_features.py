from lorad.api.utils.decorators import lrd_api_endp, lrd_auth
import lorad.common.utils.globs as globs
from lorad.common.utils.misc import read_config

ENDP_PATH = "/enabled_features"
LOGIN_REQUIRED = True
DOCSTRING = {"GET": "Returns features enabled in the backend."}
RESULT_EXAMPLE = "{'features': ['REST', 'RESTREAMER', 'FILESTREAMER', 'FILESTREAMER:YANDEX']}"

@lrd_auth(globs.CAP_BASIC_USER)
@lrd_api_endp
def impl_GET(headers):
    config = read_config()
    return {'features': config["ENABLED_FEATURES"]}