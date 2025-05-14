from lorad.api.utils.decorators import lrd_api_endp, lrd_auth
from lorad.api.utils.misc import get_stations
import lorad.common.utils.globs as globs

ENDP_PATH = "/yandex/radios"

@lrd_api_endp
@lrd_auth(globs.CAP_BASIC_USER)
def impl_GET(headers):
    return get_stations()