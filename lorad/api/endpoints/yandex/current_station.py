from lorad.api.utils.decorators import lrd_api_endp, lrd_auth
import lorad.common.utils.globs as globs

ENDP_PATH = "/yandex/current_station"

@lrd_api_endp
@lrd_auth(globs.CAP_BASIC_USER)
def impl_GET(headers):
    return {"station": globs.RADIO_YAMU.radio.station_id}