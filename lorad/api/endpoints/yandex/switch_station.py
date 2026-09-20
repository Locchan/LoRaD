from lorad.api.endpoints.users.auth import lrd_validate
from lorad.api.utils.decorators import lrd_api_endp, lrd_auth, lrd_feat_req
from lorad.api.utils.misc import get_current_player, forbid_switching
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
    player = get_current_player()
    if player is None or player.name_tech != globs.FILESTREAMER.name_tech:
        return {"rc": 406, "data": {"message": "Yandex is not the current player."}}
    stations = player.list_sources()
    if stations is None:
        return {"rc": 406, "data": {"message": "Yandex is not initialized."}}
    if globs.SWITCH_LOCK:
        return {"rc": 406, "data": {"message": "Cannot switch right now. Try later."}}
    if data["new_station"] not in stations.values():
        return f"There is no such station: {data['new_station']}"
    return

@lrd_auth(globs.CAP_ADMIN)
@lrd_feat_req(FEAT_FILESTREAMER_YANDEX)
@lrd_validate(validate)
@lrd_api_endp
def impl_POST(headers, data):
    get_current_player().switch_source(data["new_station"])
    forbid_switching(10)
    return {"success": True}
