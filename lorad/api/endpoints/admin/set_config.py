import json
import re

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
_RE_HHMM = re.compile(r'^(?:[01]?\d|2[0-3]):[0-5]\d$')

def _validate_time(times_list):
    for atime in times_list:
        if not isinstance(atime, str):
            return False
        if _RE_HHMM.match(atime):
            continue
        else:
            return False
    return True

def validate(headers, data):
    for areq in REQUIRED_FIELDS['POST']:
        if areq not in data or areq == "":
            return f"This method requires {REQUIRED_FIELDS['POST']} to be specified."
    data_key = data["key"]
    data_key_lower = data_key.lower()
    sensitive_words = ("username", "password", "token", "key", "private", "address", "database", "auth")
    if any(word in data_key_lower for word in sensitive_words):
        return "Nah."
    if data["key"] not in EDITABLE_CONFIG_KEYS:
        return f"{data["key"]} is not configured at all or not configured to be editable."

    if data["key"] == "ENABLED_PROGRAMS/NewsSmall/start_times":
        try:
            value_parsed = data['value']
            if not _validate_time(value_parsed):
                raise RuntimeError("Invalid time format")
        except Exception:
            return "'value' should be a valid JSON list of times (e.g. ['10:00', '11:00'])."

    config_path_split = data_key.split("/")
    config_data = read_config()
    for akey in config_path_split:
        if akey in config_data:
            config_data = config_data[akey]
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
    if data["key"] == "ENABLED_PROGRAMS/NewsSmall/start_times":
        register_programs(reload=True)
    return {"success": True}

