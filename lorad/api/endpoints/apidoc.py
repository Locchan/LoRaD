from lorad.api.utils.apidoc import get_apidoc
from lorad.api.endpoints.users.auth import lrd_validate
from lorad.api.orm.User import user_register
from lorad.api.utils.decorators import lrd_api_endp, lrd_auth
import lorad.common.utils.globs as globs

ENDP_PATH = "/apidoc"
LOGIN_REQUIRED = False
REQUIRED_FIELDS = {}
OPTIONAL_FIELDS = {"POST": ["format"]}
VALID_FORMATS = ["plain", "html"]
DOCSTRING = {"POST": f"Returns the documentation for this API. Known formats: {', '.join(VALID_FORMATS)}",
             "GET": "Returns the documentation for this API."}

def validate(headers, data):
    for areq in REQUIRED_FIELDS['POST']:
        if areq not in data or areq == "":
            return f"This method requires {REQUIRED_FIELDS['POST']} to be specified."
    if data["format"] not in VALID_FORMATS:
        return f"Format {data["format"]} is unknown."
    return

@lrd_api_endp
def impl_GET(headers):
    return get_apidoc()

@lrd_api_endp
@lrd_validate(validate)
def impl_POST(headers, data):
    format = "plain"
    if "format" in data:
        format = data["format"]
    return get_apidoc(format)
