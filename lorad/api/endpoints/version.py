from api.utils.decorators import lrd_api_endp


__path = "/version"


@lrd_api_endp
def __impl(data: dict):
    from common.utils
    return {}