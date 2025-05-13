from atexit import register
from lorad.api.endpoints.users.auth import lrd_validate
from lorad.api.orm.User import user_register
from lorad.api.utils.decorators import lrd_api_endp, lrd_auth
from lorad.api.utils.misc import get_username_from_headers
from lorad.common.utils.globs import CAP_ADMIN

ENDP_PATH = "/user/register"

def validate(headers, data):
    required_fields = ["username", "password"]
    for areq in required_fields:
        if areq not in data or areq == "":
            return f"This method requires {required_fields} to be specified."
    if len(data["username"]) < 3:
        return "The username should be at least 3 characters"
    if len(data["password"]) < 8:
        return "The password has to be at least 8 characters"
    return

@lrd_api_endp
@lrd_validate(validate)
@lrd_auth(CAP_ADMIN)
def impl_POST(headers, data):
    register_result = user_register(data["username"], data["password"])
    if register_result is None:
        return (500, {"error": "Unknown error"})
    if register_result:
        return {"success": True}
    else:
        return (409, {"error": f"User {data["username"]} already exists"})
