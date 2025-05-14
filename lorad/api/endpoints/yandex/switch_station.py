from lorad.api.endpoints.users.auth import lrd_validate
from lorad.api.orm.User import user_register
from lorad.api.utils.decorators import lrd_api_endp, lrd_auth
from lorad.api.utils.misc import get_stations
import lorad.common.utils.globs as globs

ENDP_PATH = "/yandex/switch_station"

def validate(headers, data):
    required_fields = ["new_station"]
    for areq in required_fields:
        if areq not in data or areq == "":
            return f"This method requires {required_fields} to be specified."
    found = [key for key, value in get_stations().items() if value == data["new_station"]]
    if not found:
        return f"There is no such station: {data["new_station"]}"
    return

@lrd_api_endp
@lrd_validate(validate)
@lrd_auth(globs.CAP_BASIC_USER)
def impl_POST(headers, data):
    globs.RADIO_STREAMER.stop_carousel()
    globs.RADIO_YAMU.radio.start_radio(data["new_station"])
    globs.RADIO_STREAMER.start_carousel()
    return {"success": True}
