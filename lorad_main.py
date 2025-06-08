#!/usr/bin/env python3

import glob
from http.server import ThreadingHTTPServer
import os
import signal
from threading import Thread
from time import sleep
import lorad.common.utils.globs as globs
from lorad.radio.programs.news.neuro.neuronews import neurify_news
from lorad.radio.programs.news.newsparser import parse_news
from lorad.radio.programs.program_mgr import prg_sched_loop
from lorad.common.utils.logger import get_logger, setdebug
from lorad.common.utils.misc import feature_enabled, read_config, signal_stop, splash
from lorad.radio.stream.ReStreamer import ReStreamer

logger = get_logger()

signal.signal(signal.SIGTERM, signal_stop)
signal.signal(signal.SIGINT, signal_stop)

splash()

logger.info("Loading config...")
config = read_config("config.json")

globs.FEATURE_FLAGS = config["FEATURE_FLAGS"] if "FEATURE_FLAGS" in config else []

if len(globs.FEATURE_FLAGS) > 0:
    logger.info(f"Enabled flags: {globs.FEATURE_FLAGS}")
    if "DEBUG" in globs.FEATURE_FLAGS:
        setdebug()

carousel_providers = []

globs.TEMPDIR = config["TEMPDIR"]

from lorad.radio.server import LoRadSrv
from lorad.radio.stream.FileStreamer import FileStreamer
from lorad.radio.sources.yandex.YaMu import YaMu
from lorad.radio.server.LoRadSrv import LoRadServer

logger.info("Starting LoRaD...")
server = ThreadingHTTPServer(("0.0.0.0", config["LISTEN_PORT"]), LoRadServer)
logger.info(f"Enabled features: {config['ENABLED_FEATURES']}")

PLAYERS = []

enabled_threads = [
    Thread(name="HTTPServer", target=LoRadSrv.start, args=(server,)),
]

if feature_enabled(globs.FEAT_FILESTREAMER):
    if feature_enabled(globs.FEAT_FILESTREAMER_YANDEX):
        globs.RADIO_YANDEX = YaMu(config["YAMU_TOKEN"], config["BITRATE_KBPS"])
        carousel_providers.append(globs.RADIO_YANDEX)
    if len(carousel_providers) > 1:
        globs.RADIO_STREAMER = FileStreamer(carousel_providers, server)
        enabled_threads.append(Thread(name="Streamer", target=globs.RADIO_STREAMER.carousel))
        PLAYERS.append(globs.RADIO_STREAMER)
    else:
        logger.error("Filesteamer is enabled but no providers are configured!")

if feature_enabled(globs.FEAT_RESTREAMER):
    globs.RESTREAMER = ReStreamer(server)
    default_station = config["RESTREAMER"]["STATION"] if "RESTREAMER" in config and "STATION" in config["RESTREAMER"] else "default"
    globs.RESTREAMER.current_station = default_station
    enabled_threads.append(Thread(name="ReStreamer", target=globs.RESTREAMER.standby))
    PLAYERS.append(globs.RESTREAMER)

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
players_num = len(PLAYERS)
if players_num == 0:
    logger.error("No players are ready after all threads are started. Nothing to play. Exiting...")
    exit(1)
else:
    logger.info(f"{players_num} players registered: {', '.join(x.__class__.__name__ for x in PLAYERS)}")
    logger.info("Defaulting to the first player")
    PLAYERS[0].start()

while True:
    for athread in enabled_threads:
        if not athread.is_alive:
            logger.error(f"A thread named [{athread.name}] died! Crashing!")
            os._exit(1)
    sleep(5)
