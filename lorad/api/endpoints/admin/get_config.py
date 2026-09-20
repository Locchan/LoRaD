from lorad.api.utils.decorators import lrd_api_endp, lrd_auth, lrd_validate
from lorad.common.utils import globs
from lorad.common.utils.misc import read_config

ENDP_PATH = "/admin/get_config"
LOGIN_REQUIRED = True
REQUIRED_FIELDS = {"GET": ["key"]}
OPTIONAL_FIELDS = {}
DOCSTRING = {"GET": "Returns the value of a configuration entry. Pass the slash-separated path as ?key=."}
RESULT_EXAMPLE = {"GET": "{'ENABLED_PROGRAMS/NewsSmall/start_times': ['10:00','11:00','14:00','15:00','16:00','17:00']}"}


def validate(headers, data=None):
    data = data or {}
    if not data.get("key"):
        return "This method requires 'key' to be specified."
    data_key = data["key"]
    data_key_lower = data_key.lower()
    sensitive_words = ("username", "password", "token", "key", "private", "address", "database", "auth")
    if any(word in data_key_lower for word in sensitive_words):
        return {"rc": 401, "data": {"message": "Nah."}}
    result = read_config()
    for akey in data_key.split("/"):
        if akey in result:
            result = result[akey]
        else:
            return {"rc": 404, "data": {"message": f"Could not find key {akey}"}}
    return


@lrd_auth(globs.CAP_ADMIN)
@lrd_validate(validate)
@lrd_api_endp
def impl_GET(headers, data=None):
    data = data or {}
    result = read_config()
    for akey in data["key"].split("/"):
        result = result[akey]
    return {data["key"]: result}
