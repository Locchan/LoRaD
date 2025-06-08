from lorad.api.endpoints.users.auth import lrd_validate
from lorad.api.utils.decorators import lrd_api_endp, lrd_auth
from lorad.api.utils.misc import get_yandex_stations
import lorad.common.utils.globs as globs

ENDP_PATH = "/yandex/switch_station"
LOGIN_REQUIRED = True
DOCSTRING = {"POST": "Switches the station"}
REQUIRED_FIELDS = {
    "POST": ["new_station"]
}
OPTIONAL_FIELDS = {}

def validate(headers, data):
    for areq in REQUIRED_FIELDS["POST"]:
        if areq not in data or areq == "":
            return f"This method requires {REQUIRED_FIELDS['POST']} to be specified."
    found = [key for key, value in get_yandex_stations().items() if value == data["new_station"]]
    if not found:
        return f"There is no such station: {data["new_station"]}"
    return

@lrd_api_endp
@lrd_validate(validate)
@lrd_auth(globs.CAP_BASIC_USER)
def impl_POST(headers, data):
    globs.RADIO_STREAMER.stop_carousel()
    globs.RADIO_YANDEX.radio.start_radio(data["new_station"])
    globs.RADIO_STREAMER.start_carousel()
    return {"success": True}
