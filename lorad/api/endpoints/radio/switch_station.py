from lorad.api.endpoints.users.auth import lrd_validate
from lorad.api.utils.decorators import lrd_api_endp, lrd_auth, lrd_feat_req
from lorad.api.utils.misc import get_yandex_stations, get_radio_stations, forbid_switching
import lorad.common.utils.globs as globs
from lorad.common.utils.globs import FEAT_FILESTREAMER_YANDEX

ENDP_PATH = "/radio/switch_station"
LOGIN_REQUIRED = True
DOCSTRING = {"POST": "Switches the station. Get available stations from /radio/available_stations"}
REQUIRED_FIELDS = {
    "POST": ["new_station"]
}
OPTIONAL_FIELDS = {}

def validate(headers, data):
    for areq in REQUIRED_FIELDS["POST"]:
        if areq not in data or areq == "":
            return f"This method requires {REQUIRED_FIELDS['POST']} to be specified."
    stations = get_radio_stations()
    found = False
    for astation in stations:
        if stations[astation] == data["new_station"]:
            found = True
    if globs.CURRENT_PLAYER_NAME != globs.RESTREAMER.name_tech:
        return {"rc": 406, "data": {"message": "Radio is not the current player."}}
    if globs.SWITCH_LOCK:
        return {"rc": 406, "data": {"message": "Cannot switch right now. Try later."}}
    if not found:
        return f"There is no such station: {data["new_station"]}"
    return

@lrd_auth(globs.CAP_ADMIN)
@lrd_feat_req(globs.FEAT_RESTREAMER)
@lrd_validate(validate)
@lrd_api_endp
def impl_POST(headers, data):
    globs.RESTREAMER.stop()
    globs.RESTREAMER.current_station = data["new_station"]
    globs.RESTREAMER.start()
    forbid_switching(10)
    return {"success": True}
