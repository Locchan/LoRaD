from lorad.api.utils.decorators import lrd_api_endp, lrd_auth
from lorad.api.utils.misc import get_yandex_stations
import lorad.common.utils.globs as globs

ENDP_PATH = "/yandex/available_stations"
LOGIN_REQUIRED = True
DOCSTRING = {"GET": "Returns available radio stations from Yandex."}
RESULT_EXAMPLE = "{'Pop':'genre:pop','Meditation':'genre:meditation'}"

@lrd_api_endp
@lrd_auth(globs.CAP_BASIC_USER)
def impl_GET(headers):
    return get_yandex_stations()