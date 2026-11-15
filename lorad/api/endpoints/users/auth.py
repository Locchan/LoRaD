from lorad.api.orm.Token import gen_token
from lorad.api.orm.User import user_login
from lorad.api.utils.decorators import lrd_api_endp, lrd_validate
import lorad.common.utils.globs as globs
from lorad.common.utils.logger import get_logger

ENDP_PATH = "/user/auth"
LOGIN_REQUIRED = False
DOCSTRING = {
        "POST": "Authenticates a user and returns an auth token"
}
RESULT_EXAMPLE = {"POST": "{'token': 'abcdefghi'}"}
REQUIRED_FIELDS = {
    "POST": ["username", "password"]
}
OPTIONAL_FIELDS = {}
logger = get_logger()

def validate(headers, data):
    for areq in REQUIRED_FIELDS["POST"]:
        if areq not in data or areq == "":
            return f"This method requires {REQUIRED_FIELDS['POST']} to be specified."
    return

@lrd_validate(validate_func=validate)
@lrd_api_endp
def impl_POST(headers, data):
    login_result = user_login(data['username'], data["password"])
    if login_result != globs.LOGIN_SUCCESS:
        logger.info(f"Attempt to log in as {data['username']} failed.")
        return (401, {"error": "Authentication failed"})
    logger.info(f"{data['username']} logged in.")
    return {"token": gen_token(data['username'])}
