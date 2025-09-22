import json

from lorad.api.endpoints.users.auth import lrd_validate
from lorad.api.utils.decorators import lrd_api_endp, lrd_auth
from lorad.common.utils import globs
from lorad.common.utils.misc import read_config

ENDP_PATH = "/admin/get_config"
LOGIN_REQUIRED = False
REQUIRED_FIELDS = {"POST": ["key"]}
OPTIONAL_FIELDS = {}
DOCSTRING = {"POST": "Returns the value of the configuration entry."}
RESULT_EXAMPLE = {"POST": "{'ENABLED_PROGRAMS/NewsSmall/start_times': ['10:00','11:00','14:00','15:00','16:00','17:00']}"}

def validate(headers, data):
    for areq in REQUIRED_FIELDS['POST']:
        if areq not in data or areq == "":
            return f"This method requires {REQUIRED_FIELDS['POST']} to be specified."
    data_key = data["key"]
    data_key_lower = data_key.lower()
    sensitive_words = ("username", "password", "token", "key", "private", "address", "database", "auth")
    if any(word in data_key_lower for word in sensitive_words):
        return {"rc": 401, "data": {"message": "Nah."}}
    config_path_split = data_key.split("/")
    data_check = read_config()
    for akey in config_path_split:
        if akey in data_check:
            data_check = data_check[akey]
        else:
            return {"rc": 404, "data": {"message": f"Could not find key {akey}"}}
    return

@lrd_auth(globs.CAP_ADMIN)
@lrd_validate(validate)
@lrd_api_endp
def impl_POST(headers, data):
    config_path_split = data["key"].split("/")
    result = read_config()
    for akey in config_path_split:
        result = result[akey]
    return json.dumps({data["key"]: result})

