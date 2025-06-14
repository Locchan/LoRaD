from lorad.api.utils.decorators import lrd_api_endp, lrd_auth
import lorad.common.utils.globs as globs

ENDP_PATH = "/yandex/current_station"
LOGIN_REQUIRED = True
DOCSTRING = {"GET": "Returns the current station."}
RESULT_EXAMPLE = "{'station': 'genre:pop'}"

@lrd_api_endp
@lrd_auth(globs.CAP_BASIC_USER)
def impl_GET(headers):
    return {"station": globs.RADIO_YANDEX.radio.station_id}