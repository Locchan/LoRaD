from lorad.api.endpoints.users.auth import lrd_validate
from lorad.api.utils.decorators import lrd_api_endp, lrd_auth, lrd_feat_req
from lorad.api.utils.misc import get_yandex_stations
import lorad.common.utils.globs as globs
from lorad.common.utils.globs import FEAT_FILESTREAMER_YANDEX

ENDP_PATH = "/yandex/switch_station"
LOGIN_REQUIRED = True
DOCSTRING = {"POST": "Switches the station. Get stations from /yandex/available_stations"}
REQUIRED_FIELDS = {
    "POST": ["new_station"]
}
OPTIONAL_FIELDS = {}

def validate(headers, data):
    for areq in REQUIRED_FIELDS["POST"]:
        if areq not in data or areq == "":
            return f"This method requires {REQUIRED_FIELDS['POST']} to be specified."
    stations = get_yandex_stations()
    if stations is None:
        return {"rc": 406, "data": {"message": "Yandex is not initialized."}}
    if globs.CURRENT_PLAYER_NAME != globs.FILESTREAMER.name_tech:
        return {"rc": 406, "data": {"message": "Yandex is not the current player."}}
    found = False
    for astation in stations:
        if stations[astation] == data["new_station"]:
            found = True
    if not found:
        return f"There is no such station: {data["new_station"]}"
    return

@lrd_auth(globs.CAP_ADMIN)
@lrd_feat_req(FEAT_FILESTREAMER_YANDEX)
@lrd_validate(validate)
@lrd_api_endp
def impl_POST(headers, data):
    globs.FILESTREAMER.stop_carousel()
    globs.YANDEX_OBJ.radio.start_radio(data["new_station"])
    globs.FILESTREAMER.start_carousel()
    return {"success": True}
