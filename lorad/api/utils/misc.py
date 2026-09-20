import hashlib
import threading
from threading import Thread
from time import sleep

import lorad.common.utils.globs as globs
from lorad.common.utils.logger import get_logger

logger = get_logger()

def whatsplaying():
    player = get_current_player()
    if player is None:
        return "None. Should not happen. This is a bug."
    return player.currently_playing

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

def switch_players(new_player_name, start=True):
    from lorad.audio.hub import get_hub
    from lorad.common.utils.logger import get_logger
    logger = get_logger()
    if new_player_name == globs.CURRENT_PLAYER_NAME:
        logger.info("The new player is the same as the old one. Nothing to do.")
        return
    logger.info(f"Switching players: from '{globs.CURRENT_PLAYER_NAME}' to '{new_player_name}'.")
    prev_player = get_current_player()
    globs.CURRENT_PLAYER_NAME = new_player_name
    new_player = get_current_player()
    if prev_player is not None:
        prev_player.stop()
        get_hub().release(prev_player)
    if start and new_player is not None:
        new_player.start()
        get_hub().acquire(new_player)

def start_player(player_name):
    from lorad.audio.hub import get_hub
    from lorad.common.utils.logger import get_logger
    logger = get_logger()
    logger.info(f"Starting player: '{player_name}'")
    if get_current_player() is not None:
        switch_players(player_name)
        return
    globs.CURRENT_PLAYER_NAME = player_name
    player = get_current_player()
    player.start()
    get_hub().acquire(player)

def get_username_from_headers(headers):
    return headers["Authorization"].split(",")[0]

def hash_password(password):
    return hashlib.sha512(password.encode('utf-8') + "Mei8HrFsNkEnEXs$J5#q22DA4hdZZ#4964EEvYL2$4G4WDRBJ%z&&Nfg8&EBxRHK".encode("utf-8")).hexdigest()

def thread_alive(thread_name):
    for thread in threading.enumerate():
        if thread.name == thread_name:
            if thread.is_alive():
                return True
    return False

def forbid_switching(time_seconds=0):
    logger.debug("Forbidding switching")
    if time_seconds > 0:
        globs.SWITCH_LOCK = True
        if not thread_alive("SW_Locker"):
            Thread(target=_switch_lock, args=(time_seconds,), name="SW_Locker").start()
    else:
        globs.SWITCH_LOCK = True

def _switch_lock(time_seconds):
    logger.debug(f"Sleeping for {time_seconds} seconds before allowing switching.")
    sleep(time_seconds)
    logger.debug("Allowing switching")
    globs.SWITCH_LOCK = False

def allow_switching():
    logger.debug("Allowing switching")
    globs.SWITCH_LOCK = False