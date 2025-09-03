from lorad.api.utils.decorators import lrd_api_endp, lrd_auth
import lorad.common.utils.globs as globs

ENDP_PATH = "/locale"
LOGIN_REQUIRED = True
DOCSTRING = {"GET": "Returns the server locale (language)."}
RESULT_EXAMPLE = {"GET": "{'locale': 'RU'}"}

@lrd_auth(globs.CAP_BASIC_USER)
@lrd_api_endp
def impl_GET(headers):
    return {"locale": globs.LOCALE}