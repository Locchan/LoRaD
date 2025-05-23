from lorad.api.utils.decorators import lrd_api_endp, lrd_auth
import lorad.common.utils.globs as globs

ENDP_PATH = "/whatsplaying"
LOGIN_REQUIRED = True
DOCSTRING = {"GET": "Returns the currently playing track/program/file/etc."}
RESULT_EXAMPLE = "{'playing': 'Darude - Sandstorm'}"

@lrd_api_endp
@lrd_auth(globs.CAP_BASIC_USER)
def impl_GET(headers):
    return {"playing": globs.RADIO_STREAMER.currently_playing}