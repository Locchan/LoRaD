from lorad.api.utils.decorators import lrd_api_endp, lrd_auth, lrd_feat_req
import lorad.common.utils.globs as globs

ENDP_PATH = "/yandex/current_station"
LOGIN_REQUIRED = True
DOCSTRING = {"GET": "Returns the current station."}
RESULT_EXAMPLE = {"GET": "{'station': 'genre:pop'}"}

@lrd_auth(globs.CAP_BASIC_USER)
@lrd_feat_req(globs.FEAT_FILESTREAMER_YANDEX)
@lrd_api_endp
def impl_GET(headers):
    if globs.YANDEX_OBJ.radio is not None:
        return {"station": globs.YANDEX_OBJ.radio.station_id}
    else:
        return {"rc": 406, "data": {"message": "Yandex is not initialized."}}