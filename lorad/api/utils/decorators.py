from lorad.api.orm.Token import check_caps, validate_token
from lorad.common.utils.logger import get_logger
from lorad.common.utils.misc import read_config

logger = get_logger()

###
#    Preferred decorator order
#    - @lrd_auth
#    - @lrd_feat_req
#    - @lrd_validate
#    - @lrd_api_endp
###

# All decorators that are above @lrd_api_endp should return responses in the raw format
#  Example: {"rc": "200", "data": {"success": True}}
# All decorators below @lrd_api_endp are shielded by @lrd_api_endp's data handler so these can return whatever.

# Makes endpoint inaccessible if a feature (or a range of features) is/are not enabled.
#  Preferably to be used on top of any other decorators.
# feat_needed can be a single string or a list of strings.
# Features are defined in the glob module.
def lrd_feat_req(feat_needed):
    def decorator(func):
        def lrd_wrp_endp(*args, **kwargs):
            config = read_config()
            if isinstance(feat_needed, str):
                if feat_needed in config["ENABLED_FEATURES"]:
                    return func(*args, **kwargs)
            elif isinstance(feat_needed, list):
                for afeature in feat_needed:
                    if afeature in config["ENABLED_FEATURES"]:
                        return func(*args, **kwargs)
            return {"rc": 405, "data": {"error": f"{feat_needed} feature is not enabled. Enable it in order to use this endpoint."}}
        return lrd_wrp_endp
    return decorator

# Default wrapper for API endpoints. All endpoints should be decorated with this.
# Handles errors and responses so that the function can just shit out whatever or crash in any way
#  and the function will make a valid JSON response out of this.
def lrd_api_endp(func):
    def lrd_wrp_endp(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            if isinstance(result, tuple):
                return {"rc": result[0], "data": result[1]}
            elif isinstance(result, dict):
                if "rc" in result:
                    return result
                else:
                    return {"rc": 200, "data": result}
            elif isinstance(result, str):
                return {"rc": 200, "data": result}
            else:
                return {"rc": 500, "data": {"error": "Incorrect output from the endpoint function."}}
        except Exception as e:
            logger.exception(e)
            return {"rc": 500, "data": {"error": f"Error ({e.__class__.__name__}). Details are in the server log."}}
    return lrd_wrp_endp

# Validates the input data and returns 400 if the validation does not pass
# Consumes a validation function which will do the actual validation and return errors.
#  Note: the good result is 'None', anything else returned by the validation function will mean an error.
def lrd_validate(validate_func):
    def decorator(func):
        def lrd_wrp_endp(*args, **kwargs):
            validate_error = validate_func(*args, **kwargs)
            if isinstance(validate_error, dict):
                if "rc" in validate_error:
                    return validate_error
            if validate_error is not None:
                return {"rc": 400, "data": {"error": validate_error}}
            else:
                return func(*args, **kwargs)
        return lrd_wrp_endp
    return decorator

# Makes an endpoint require authentication as well as require the authenticated user have some specific capability.
# Consumes a capability. Capabilities are defined in the glob module.
def lrd_auth(cap_required):
    def decorator(func):
        def lrd_wrp_endp(*args, **kwargs):
            headers = dict(args[0]._headers)
            if "Authorization" in headers:
                auth_split = headers["Authorization"].split(",")
                if len(auth_split) != 2:
                    return {"rc": 400, "data": {"error": "Incorrect 'Authorization' header."}}
                valid = validate_token(auth_split[0].strip(), auth_split[1].strip())
                if valid:
                    if check_caps(auth_split[0], cap_required):
                        return func(*args, **kwargs)
                    else:
                        return {"rc": 401, "data": {"error": "Insufficient permissions"}}
                else:
                    return {"rc": 401, "data": {"error": "Unauthorized"}}
            else:
                return {"rc": 401, "data": {"error": "Unauthorized"}}
        return lrd_wrp_endp
    return decorator