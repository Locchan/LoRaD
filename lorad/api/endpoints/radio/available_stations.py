from lorad.api.utils.decorators import lrd_api_endp, lrd_auth, lrd_feat_req
from lorad.api.utils.misc import get_radio_stations
import lorad.common.utils.globs as globs

ENDP_PATH = "/radio/available_stations"
LOGIN_REQUIRED = True
DOCSTRING = {"GET": "Returns available radio stations."}
RESULT_EXAMPLE = {"GET": "{'love': 'Love Radio','euro': 'Euroradio'}"}

@lrd_auth(globs.CAP_BASIC_USER)
@lrd_feat_req(globs.FEAT_RESTREAMER)
@lrd_api_endp
def impl_GET(headers):
    return get_radio_stations()