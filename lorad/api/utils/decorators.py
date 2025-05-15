from lorad.api.orm.Token import check_caps, validate_token
from lorad.common.utils.logger import get_logger

logger = get_logger()

def lrd_api_endp(func):
    def lrd_wrp_endp(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            if isinstance(result, tuple):
                return {"rc": result[0], "data": result[1]}
            if isinstance(result, dict) or isinstance(result, str):
                return {"rc": 200, "data": result}
            return {"rc": 500, "data": {"error": "Incorrect output from the endpoint function."}}
        except Exception as e:
            logger.exception(e)
            return {"rc": 500, "data": {"error": f"Error ({e.__class__.__name__}). Details are in the server log."}}
    return lrd_wrp_endp


def lrd_validate(validate_func):
    def decorator(func):
        def lrd_wrp_endp(*args, **kwargs):
            validate_error = validate_func(*args, **kwargs)
            if validate_error is not None:
                return (400, {"error": validate_error})
            else:
                return func(*args, **kwargs)
        return lrd_wrp_endp
    return decorator


def lrd_auth(cap_required):
    def decorator(func):
        def lrd_wrp_endp(*args, **kwargs):
            headers = dict(args[0]._headers)
            if "Authorization" in headers:
                auth_split = headers["Authorization"].split(",")
                if len(auth_split) != 2:
                    return (400, {"error": "Incorrect 'Authorization' header."})
                valid = validate_token(auth_split[0].strip(), auth_split[1].strip())
                if valid:
                    if check_caps(auth_split[0], cap_required):
                        return func(*args, **kwargs)
                    else:
                        return (401, {"error": "Insufficient permissions"})
                else:
                    return (401, {"error": "Unauthorized"})
            else:
                return (401, {"error": "Unauthorized"})
        return lrd_wrp_endp
    return decorator