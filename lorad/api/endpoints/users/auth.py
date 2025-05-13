from lorad.api.orm import Token, User
from lorad.api.utils.decorators import lrd_api_endp, lrd_validate
from lorad.common.utils.globs import *
from lorad.common.utils.logger import get_logger

ENDP_PATH = "/user/auth"
logger = get_logger()

def validate(headers, data):
    required_fields = ["username", "password"]
    for areq in required_fields:
        if areq not in data or areq == "":
            return f"This method requires {required_fields} to be specified."
    return

@lrd_api_endp
@lrd_validate(validate_func=validate)
def impl_POST(headers, data):
    login_result = User.user_login(data["username"], data["password"])
    if login_result == LOGIN_NO_SUCH_USER:
        logger.info(f"Attempt to log in as {data["username"]} failed: No such user.")
        return (401, {"error": "Login failed"})
    if login_result == LOGIN_INCORRECT_PASSWORD:
        logger.info(f"Attempt to log in as {data["username"]} failed: Incorrect password.")
        return (401, {"error": "Login failed"})
    if login_result == LOGIN_SUCCESS:
        logger.info(f"{data["username"]} logged in.")
        return {"token": Token.gen_token(data["username"])}
    logger.error(f"Attempt to log in as {data["username"]} failed: Invalid response from login method.")
    return (401, {"error": "Login failed"})