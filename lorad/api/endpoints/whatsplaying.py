from lorad.api.utils.decorators import lrd_api_endp, lrd_auth
import lorad.common.utils.globs as globs
from lorad.api.utils.misc import whatsplaying, get_current_player, get_yandex_stations

ENDP_PATH = "/whatsplaying"
LOGIN_REQUIRED = True
DOCSTRING = {"GET": "Returns the currently playing track/program/file/etc."}
RESULT_EXAMPLE = {"GET": "{'player': 'Radio Player', 'playing': 'Радио \"Культура\"'}"}

@lrd_auth(globs.CAP_BASIC_USER)
@lrd_api_endp
def impl_GET(headers):
    response = {
        "player_readable": get_current_player().name_readable,
        "player_tech": get_current_player().name_tech,
        "playing": whatsplaying()
    }

    if globs.CURRENT_PLAYER_NAME == globs.FILESTREAMER.name_tech:
        response["station_tech"] = get_current_player().current_ride.radio.station_id
        stations = get_yandex_stations(cached=True)
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