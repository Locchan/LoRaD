#!/usr/bin/env python3

from http.server import ThreadingHTTPServer
import os
import signal
from threading import Thread
from time import sleep
import lorad.common.utils.globs as globs
from lorad.api.utils.misc import start_player
from lorad.audio.programs.news.neuro.neuronews import neurify_news
from lorad.audio.programs.news.newsparser import parse_news
from lorad.audio.programs.program_mgr import prg_sched_loop
from lorad.common.localization.localization import init_localization
from lorad.common.utils.logger import get_logger, setdebug
from lorad.common.utils.misc import feature_enabled, read_config, signal_stop, splash
from lorad.audio.sources.RadReStreamer import RadReStreamer

logger = get_logger()

signal.signal(signal.SIGTERM, signal_stop)
signal.signal(signal.SIGINT, signal_stop)

splash()

logger.info("Loading config...")
config = read_config()

init_localization()

globs.FEATURE_FLAGS = config["FEATURE_FLAGS"] if "FEATURE_FLAGS" in config else []

if len(globs.FEATURE_FLAGS) > 0:
    logger.info(f"Enabled flags: {globs.FEATURE_FLAGS}")
    if "DEBUG" in globs.FEATURE_FLAGS or "DEBUG" in config and config["DEBUG"]:
        setdebug()

carousel_providers = []

globs.TEMPDIR = config["TEMPDIR"]

from lorad.audio.server import AudioStream
from lorad.audio.sources.FileStreamer import FileStreamer
from lorad.audio.file_sources.yandex.YaMu import YaMu

logger.info("Starting LoRaD...")
globs.CURRENT_DATA_STREAMER = ThreadingHTTPServer(("0.0.0.0", config["LISTEN_PORT"]), AudioStream.AudioStream)

logger.info(f"Enabled features: {config['ENABLED_FEATURES']}")

enabled_threads = [
    Thread(name="HTTPServer", target=AudioStream.start, args=(globs.CURRENT_DATA_STREAMER,)),
]

if feature_enabled(globs.FEAT_FILESTREAMER):
    if feature_enabled(globs.FEAT_FILESTREAMER_YANDEX):
        globs.YANDEX_OBJ = YaMu(config["YAMU_TOKEN"], config["BITRATE_KBPS"])
        carousel_providers.append(globs.YANDEX_OBJ)
    if len(carousel_providers) > 0:
        globs.FILESTREAMER = FileStreamer(carousel_providers, globs.CURRENT_DATA_STREAMER)
        enabled_threads.append(Thread(name="Streamer", target=globs.FILESTREAMER.carousel))
        globs.PLAYERS.append(globs.FILESTREAMER)
    else:
        logger.error("Filesteamer is enabled but no providers are configured!")

if feature_enabled(globs.FEAT_RESTREAMER):
    globs.RESTREAMER = RadReStreamer(globs.CURRENT_DATA_STREAMER)
    default_station = config["RESTREAMER"]["STATION"] if "RESTREAMER" in config and "STATION" in config["RESTREAMER"] else "default"
    globs.RESTREAMER.current_station = default_station
    enabled_threads.append(Thread(name="ReStreamer", target=globs.RESTREAMER.standby))
    globs.PLAYERS.append(globs.RESTREAMER)

if feature_enabled(globs.FEAT_NEURONEWS):
    enabled_threads.append(Thread(name="NewsParser", target=parse_news))
    enabled_threads.append(Thread(name="Neuro", target=neurify_news))
    enabled_threads.append(Thread(name="ProgramMgr", target=prg_sched_loop))

if feature_enabled(globs.FEAT_REST):
    from lorad.api.LoRadAPISrv import start_api_server
    enabled_threads.append(Thread(name="API", target=start_api_server))

# Sleeps are helping to avoid scrambled module startup logs
for athread in enabled_threads:
    athread.start()
    sleep(0.2)

logger.info("All threads started.")
players_num = len(globs.PLAYERS)
if players_num == 0:
    logger.error("No players are ready after all threads are started. Nothing to play. Exiting...")
    exit(1)
else:
    logger.info(f"{players_num} players registered: {', '.join(x.__class__.__name__ for x in globs.PLAYERS)}")
    logger.info("Defaulting to the first player")
    start_player(globs.PLAYERS[0].name_tech)

while True:
    for athread in enabled_threads:
        if not athread.is_alive:
            logger.error(f"A thread named [{athread.name}] died! Crashing!")
            os._exit(1)
    sleep(5)
