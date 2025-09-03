from atexit import register
from lorad.api.endpoints.users.auth import lrd_validate
from lorad.api.orm.User import user_remove
from lorad.api.utils.decorators import lrd_api_endp, lrd_auth
import lorad.common.utils.globs as globs

ENDP_PATH = "/user/remove"
LOGIN_REQUIRED = True
REQUIRED_FIELDS = {
    "POST": ["username"]
}
OPTIONAL_FIELDS = {}
DOCSTRING = {"POST": "Removes a user. You should be an admin to do this."}

def validate(headers, data):
    for areq in REQUIRED_FIELDS['POST']:
        if areq not in data or areq == "":
            return f"This method requires {REQUIRED_FIELDS['POST']} to be specified."
    if len(data["username"]) < 3:
        return "Such user cannot possibly exist"
    return

@lrd_auth(globs.CAP_ADMIN)
@lrd_validate(validate)
@lrd_api_endp
def impl_POST(headers, data):
    register_result = user_remove(data["username"])
    if register_result is None:
        return (500, {"error": "Unknown error"})
    if register_result:
        return {"success": True}
    else:
        return (404, {"error": f"User {data["username"]} not found."})
