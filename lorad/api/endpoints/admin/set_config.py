import json

from lorad.api.endpoints.users.auth import lrd_validate
from lorad.api.utils.decorators import lrd_api_endp, lrd_auth
from lorad.audio.programs.program_mgr import register_programs
from lorad.common.utils import globs
from lorad.common.utils.misc import read_config, write_config

ENDP_PATH = "/admin/set_config"
LOGIN_REQUIRED = False
REQUIRED_FIELDS = {"POST": ["key", "value"]}
OPTIONAL_FIELDS = {}
EDITABLE_CONFIG_KEYS = ["ENABLED_PROGRAMS/NewsSmall/start_times"]
DOCSTRING = {"POST": "Sets a config entry to a value."}

def validate(headers, data):
    for areq in REQUIRED_FIELDS['POST']:
        if areq not in data or areq == "":
            return f"This method requires {REQUIRED_FIELDS['POST']} to be specified."
    data_key = data["key"]
    data_key_lower = data_key.lower()
    sensitive_words = ("username", "password", "token", "key", "private", "address", "database", "auth")
    if any(word in data_key_lower for word in sensitive_words):
        return {"rc": 401, "data": {"message": "Nah."}}
    if data["key"] not in EDITABLE_CONFIG_KEYS:
        return {"rc": 401, "data": {"message": f"{data["key"]} is not configured at all or not configured to be editable."}}
    config_path_split = data_key.split("/")
    data = read_config()
    for akey in config_path_split:
        if akey in data:
            data = data[akey]
        else:
            return {"rc": 404, "data": {"message": f"Could not find key {akey}"}}
    return

@lrd_auth(globs.CAP_ADMIN)
@lrd_validate(validate)
@lrd_api_endp
def impl_POST(headers, data):
    config_path_split = data["key"].split("/")
    value = data.get("value")
    config = read_config()
    current = config
    for key in config_path_split[:-1]:
        current = current.setdefault(key, {})
    current[config_path_split[-1]] = value
    write_config(config)
    register_programs(reload=True)
    return {"success": True}

