from lorad.api.endpoints.users.auth import lrd_validate
from lorad.api.utils.decorators import lrd_api_endp, lrd_auth, lrd_feat_req
from lorad.api.utils.misc import get_players_names, switch_players, forbid_switching
import lorad.common.utils.globs as globs

ENDP_PATH = "/switch_player"
LOGIN_REQUIRED = True
DOCSTRING = {"POST": "Switches the player"}
REQUIRED_FIELDS = {
    "POST": ["new_player"]
}
OPTIONAL_FIELDS = {}

def validate(headers, data):
    for areq in REQUIRED_FIELDS["POST"]:
        if areq not in data or areq == "":
            return f"This method requires {REQUIRED_FIELDS['POST']} to be specified."
    stations = get_players_names()
    found = False
    for astation in stations:
        if astation == data["new_player"]:
            found = True
    if globs.SWITCH_LOCK:
        return {"rc": 406, "data": {"message": "Cannot switch right now. Try later."}}
    if not found:
        return f"There is no such player: {data["new_player"]}"
    return

@lrd_auth(globs.CAP_ADMIN)
@lrd_feat_req(globs.FEAT_RESTREAMER)
@lrd_validate(validate)
@lrd_api_endp
def impl_POST(headers, data):
    switch_players(data["new_player"])
    forbid_switching(10)
    return {"success": True}
