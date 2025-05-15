import inspect
from lorad.api.orm import Token, User
from lorad.api.utils.decorators import lrd_api_endp, lrd_validate
import lorad.common.utils.globs as globs
from lorad.common.utils.logger import get_logger

ENDP_PATH = "/user/auth"
LOGIN_REQUIRED = False
DOCSTRING = {
        "POST": "Authenticates a user and returns an auth token"
}
RESULT_EXAMPLE = "{'token': 'abcdefghi'}"
REQUIRED_FIELDS = {
    "POST": ["username", "password"]
}
OPTIONAL_FIELDS = {}
logger = get_logger()

def validate(headers, data):
    for areq in REQUIRED_FIELDS["POST"]:
        if areq not in data or areq == "":
            return f"This method requires {REQUIRED_FIELDS["POST"]} to be specified."
    return

@lrd_api_endp
@lrd_validate(validate_func=validate)
def impl_POST(headers, data):
    login_result = User.user_login(data["username"], data["password"])
    if login_result == globs.LOGIN_NO_SUCH_USER:
        logger.info(f"Attempt to log in as {data["username"]} failed: No such user.")
        return (401, {"error": "Login failed"})
    if login_result == globs.LOGIN_INCORRECT_PASSWORD:
        logger.info(f"Attempt to log in as {data["username"]} failed: Incorrect password.")
        return (401, {"error": "Login failed"})
    if login_result == globs.LOGIN_SUCCESS:
        logger.info(f"{data["username"]} logged in.")
        return {"token": Token.gen_token(data["username"])}
    logger.error(f"Attempt to log in as {data["username"]} failed: Invalid response from login method.")
    return (401, {"error": "Login failed"})