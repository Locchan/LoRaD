from lorad.api.utils.apidoc import get_apidoc
from lorad.api.utils.decorators import lrd_api_endp
from lorad.api.utils.openapi import generate_full_openapi_spec

ENDP_PATH = "/openapi"
LOGIN_REQUIRED = False
REQUIRED_FIELDS = {}
OPTIONAL_FIELDS = {}
DOCSTRING = {"GET": "Returns OpenAPI specification for this API."}

@lrd_api_endp
def impl_GET(headers):
    return generate_full_openapi_spec()
