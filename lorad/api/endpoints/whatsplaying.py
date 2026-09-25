import json
import time

from lorad.api.orm.Token import check_caps, validate_token
from lorad.api.utils.decorators import lrd_websocket
import lorad.common.utils.globs as globs
from lorad.common.utils.logger import get_logger
from lorad.api.utils.misc import whatsplaying, get_current_player

ENDP_PATH = "/whatsplaying"
LOGIN_REQUIRED = True
DOCSTRING = {"GET": "WebSocket stream of current player, station, and track changes. Lives on REST.WS_LISTEN_PORT, not the REST port."}
RESULT_EXAMPLE = {
    "GET": "{'player_readable': 'File Player', 'playing': 'Artist - Track', 'liked': true, 'looping': false, 'can_switch': true}"
}
logger = get_logger()
# Heartbeat when nothing else changed. Playhead is not a change.
PUSH_PERIOD_S = 30


def _can_switch(player) -> bool:
    """Whether a player/station switch would be accepted right now (see the switch endpoints)."""
    return not globs.SWITCH_LOCK and not getattr(player, "switching", False)


def _state():
    player = get_current_player()
    if player is None:
        return {
            "player_readable": None,
            "player_tech": None,
            "playing": None,
            "can_skip": False,
            "can_switch": False,
        }

    response = {
        "player_readable": player.name_readable,
        "player_tech": player.name_tech,
        "playing": whatsplaying(),
        "can_skip": bool(
            getattr(player, "supports_next_track", lambda: False)()
            and getattr(player, "running", False)
        ),
        "can_switch": _can_switch(player),
    }

    if globs.FILESTREAMER is not None and player.name_tech == globs.FILESTREAMER.name_tech:
        response["station_tech"] = player.current_source()
        response["looping"] = bool(getattr(player, "looping", False))
        # Files have a playhead; a live restream does not, so these stay absent for radio.
        length = player.track_length()
        if length:
            response["length_s"] = round(length, 1)
            response["position_s"] = round(player.track_position(), 1)
        if getattr(player, "supports_liking", lambda: False)():
            try:
                response["liked"] = bool(player.current_track_liked())
            except Exception as e:
                logger.warning(f"Could not get Yandex like status: {e}")
                response["liked"] = None
        stations = player.list_sources(cached=True) or {}
        for name, tech in globs.YANDEX_SYNTHETIC_STATIONS.items():
            if response["station_tech"] == tech:
                response["station_readable"] = name
                return response
        for astation in stations:
            if stations[astation] == response["station_tech"]:
                response["station_readable"] = astation
                break
        if "station_readable" not in response:
            response["station_readable"] = "Unknown???"

    return response


@lrd_websocket
def impl_GET(headers, ws):
    # Browsers cannot attach Authorization to a WebSocket handshake. Authenticate
    # the first frame, then never expose the token in a URL or proxy access log.
    auth_raw = ws.recv(timeout=10)
    try:
        auth = json.loads(auth_raw) if isinstance(auth_raw, str) else {}
    except json.JSONDecodeError:
        auth = {}
    username = str(auth.get("username", "")).strip()
    token = str(auth.get("token", "")).strip()
    if not validate_token(username, token) or not check_caps(username, globs.CAP_BASIC_USER):
        ws.send({"error": "Unauthorized"})
        return

    previous = None
    last_sent = 0.0
    last_auth = time.monotonic()
    while ws.open:
        now = time.monotonic()
        if now - last_auth >= 30:
            if not validate_token(username, token) or not check_caps(username, globs.CAP_BASIC_USER):
                ws.send({"error": "Unauthorized"})
                return
            last_auth = now
        state = _state()
        # The playhead moves constantly; it must not count as a change or we would push every tick.
        serialized = json.dumps(
            {key: value for key, value in state.items() if key != "position_s"}, sort_keys=True
        )
        if serialized != previous or now - last_sent >= PUSH_PERIOD_S:
            ws.send(state)
            previous = serialized
            last_sent = now
        # Also services ping/close frames. None here can simply mean timeout.
        ws.recv(timeout=0.5)