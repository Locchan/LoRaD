import hashlib
from collections import deque
from time import sleep

import lorad.common.utils.globs as globs
from lorad.audio.server import LoRadSrv
from lorad.audio.sources.FileStreamer import FileStreamer
from lorad.audio.sources.RadReStreamer import RadReStreamer


def whatsplaying():
    player = get_current_player()
    if player is None:
        return "None. Should not happen. This is a bug."
    if isinstance(player, FileStreamer) or isinstance(player, RadReStreamer):
        return player.currently_playing
    else:
        return f"Streamer {player.__class__.__name__} is not supported by whatsplaying. Implement it!"

def get_current_player():
    for aplayer in globs.PLAYERS:
        if aplayer.name_tech == globs.CURRENT_PLAYER_NAME:
            return aplayer
    return None

def get_players_names():
    res = {}
    for aplayer in globs.PLAYERS:
        res[aplayer.name_tech] = aplayer.name_readable
    return res

def switch_players(new_player_name):
    from lorad.common.utils.logger import get_logger
    logger = get_logger()
    logger.info(f"Switching players: from '{globs.CURRENT_PLAYER_NAME}' to '{new_player_name}'.")
    if new_player_name == globs.CURRENT_PLAYER_NAME:
        return
    else:
        prev_player = get_current_player()
        globs.CURRENT_PLAYER_NAME = new_player_name
        new_player = get_current_player()
        LoRadSrv.player_switch = True
        LoRadSrv.current_data = deque()
        prev_player.stop()
        sleep(1)
        new_player.start()
        LoRadSrv.player_switch = False

def start_player(player_name):
    from lorad.common.utils.logger import get_logger
    logger = get_logger()
    logger.info(f"Starting player: '{player_name}'")
    if get_current_player() is not None:
        switch_players(player_name)
    globs.CURRENT_PLAYER_NAME = player_name
    player = get_current_player()
    player.start()

def get_username_from_headers(headers):
    return headers["Authorization"].split(",")[0]

def hash_password(password):
    return hashlib.sha512(password.encode('utf-8') + "Mei8HrFsNkEnEXs$J5#q22DA4hdZZ#4964EEvYL2$4G4WDRBJ%z&&Nfg8&EBxRHK".encode("utf-8")).hexdigest()

def get_radio_stations():
    stations = globs.RESTREAMER.get_stations()
    stations_parsed = {}
    for anitem in stations:
        stations_parsed[anitem] = stations[anitem]["name"]
    return stations_parsed

def get_yandex_stations():
    stations = globs.YANDEX_OBJ.radio.get_stations()
    stations_parsed = {}
    for astation in stations:
        stations_parsed[astation['station']['name']] = f"{astation['station']['id']['type']}:{astation['station']['id']['tag']}"
    return stations_parsed