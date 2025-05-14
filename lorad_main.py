#!/usr/bin/env python3

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
from lorad.common.utils.misc import read_config, signal_stop, splash

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
from lorad.radio.stream.Streamer import Streamer
from lorad.radio.music.yandex.YaMu import YaMu
from lorad.radio.server.LoRadSrv import LoRadServer
from lorad.api.LoRadAPISrv import start_api_server

globs.RADIO_YAMU = YaMu(config["YAMU_TOKEN"], config["BITRATE_KBPS"])
carousel_providers.append(globs.RADIO_YAMU)

logger.info("Starting LoRaD...")
server = ThreadingHTTPServer(("0.0.0.0", config["LISTEN_PORT"]), LoRadServer)
logger.info(f"Enabled features: {config['ENABLED_FEATURES']}")
globs.RADIO_STREAMER = Streamer(carousel_providers, server)

enabled_threads = [
    Thread(name="Streamer", target=globs.RADIO_STREAMER.carousel),
    Thread(name="HTTPServer", target=LoRadSrv.start, args=(server,))
]

if globs.FEAT_NEURONEWS in config["ENABLED_FEATURES"]:
    enabled_threads.append(Thread(name="NewsParser", target=parse_news))
    enabled_threads.append(Thread(name="Neuro", target=neurify_news))
    enabled_threads.append(Thread(name="ProgramMgr", target=prg_sched_loop))

if globs.FEAT_REST in config["ENABLED_FEATURES"]:
    enabled_threads.append(Thread(name="API", target=start_api_server))

# Sleeps are helping to avoid scrambled module startup logs
for athread in enabled_threads:
    athread.start()
    sleep(0.2)

logger.info("All threads started.")
globs.RADIO_STREAMER.start_carousel()

while True:
    for athread in enabled_threads:
        if not athread.is_alive:
            logger.error(f"A thread named [{athread.name}] died! Crashing!")
            os._exit(1)
    sleep(5)
