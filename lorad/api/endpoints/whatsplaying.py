from lorad.api.utils.decorators import lrd_api_endp, lrd_auth
import lorad.common.utils.globs as globs
from lorad.api.utils.misc import whatsplaying, get_current_player

ENDP_PATH = "/whatsplaying"
LOGIN_REQUIRED = True
DOCSTRING = {"GET": "Returns the currently playing track/program/file/etc."}
RESULT_EXAMPLE = {"GET": "{'player': 'Radio Player', 'playing': 'Радио \"Культура\"'}"}

@lrd_auth(globs.CAP_BASIC_USER)
@lrd_api_endp
def impl_GET(headers):
    player = get_current_player()
    response = {
        "player_readable": player.name_readable,
        "player_tech": player.name_tech,
        "playing": whatsplaying()
    }

    if player.name_tech == globs.FILESTREAMER.name_tech:
        response["station_tech"] = player.current_source()
        stations = player.list_sources(cached=True) or {}
        if response["station_tech"] == "user:onyourwave":
            response["station_readable"] = "Моя волна"
            return response
        for astation in stations:
            if stations[astation] == response["station_tech"]:
                response["station_readable"] = astation
                break
        if "station_readable" not in response:
            response["station_readable"] = "Unknown???"

    return response