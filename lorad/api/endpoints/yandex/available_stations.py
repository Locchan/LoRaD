from lorad.api.utils.decorators import lrd_api_endp, lrd_auth, lrd_feat_req
from lorad.api.utils.misc import get_yandex_stations
import lorad.common.utils.globs as globs
from lorad.common.utils.globs import FEAT_FILESTREAMER_YANDEX

ENDP_PATH = "/yandex/available_stations"
LOGIN_REQUIRED = True
DOCSTRING = {"GET": "Returns available radio stations from Yandex."}
RESULT_EXAMPLE = "{'Pop':'genre:pop','Meditation':'genre:meditation'}"

@lrd_auth(globs.CAP_BASIC_USER)
@lrd_feat_req(FEAT_FILESTREAMER_YANDEX)
@lrd_api_endp
def impl_GET(headers):
    stations = get_yandex_stations()
    if stations is None:
        return {"rc": 406, "data": {"message": "Yandex is not initialized."}}