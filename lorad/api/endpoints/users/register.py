from lorad.api.endpoints.users.auth import lrd_validate
from lorad.api.orm.User import user_register
from lorad.api.utils.decorators import lrd_api_endp, lrd_auth
import lorad.common.utils.globs as globs

ENDP_PATH = "/user/register"
LOGIN_REQUIRED = True
REQUIRED_FIELDS = {
    "POST": ["username", "password"]
}
OPTIONAL_FIELDS = {}
DOCSTRING = {"POST": "Registers a user. You should be an admin to do this."}

def validate(headers, data):
    for areq in REQUIRED_FIELDS['POST']:
        if areq not in data or areq == "":
            return f"This method requires {REQUIRED_FIELDS['POST']} to be specified."
    if len(data["username"]) < 3:
        return "The username should be at least 3 characters"
    if len(data["password"]) < 8:
        return "The password has to be at least 8 characters"
    return

@lrd_auth(globs.CAP_ADMIN)
@lrd_validate(validate)
@lrd_api_endp
def impl_POST(headers, data):
    register_result = user_register(data["username"], data["password"])
    if register_result is None:
        return (500, {"error": "Unknown error"})
    if register_result:
        return {"success": True}
    else:
        return (409, {"error": f"User '{data["username"]}' already exists"})
