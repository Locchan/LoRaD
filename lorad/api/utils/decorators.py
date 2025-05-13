from lorad.common.utils.logger import get_logger

logger = get_logger()

def lrd_api_endp(func):
    def lrd_wrp_endp(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            if isinstance(result, tuple):
                return {"response": result[0], "response_data": result[1]}
            if isinstance(result, dict):
                return {"response": 200, "response_data": result}
            return {"response": 500, "response_data": "Incorrect output from the endpoint function."}
        except Exception as e:
            logger.exception(e)
            return {"response": 500, "response_data": f"Error ({e.__class__.__name__}). Details are in the server log."}
    return lrd_wrp_endp
