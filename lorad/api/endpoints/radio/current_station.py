from lorad.api.utils.decorators import lrd_api_endp, lrd_auth, lrd_feat_req
import lorad.common.utils.globs as globs

ENDP_PATH = "/radio/current_station"
LOGIN_REQUIRED = True
DOCSTRING = {"GET": "Returns the current station."}
RESULT_EXAMPLE = {"GET": "{'station': 'love'}"}

@lrd_auth(globs.CAP_BASIC_USER)
@lrd_feat_req(globs.FEAT_RESTREAMER)
@lrd_api_endp
def impl_GET(headers):
    return {"station": globs.RESTREAMER.current_station}