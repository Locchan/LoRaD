#!/usr/bin/env python3

from http.server import ThreadingHTTPServer
import os
import signal
from threading import Thread
from time import sleep
from lorad.programs.news.neuro.neuronews import neurify_news
from lorad.programs.news.newsparser import parse_news
from lorad.programs.program_mgr import prg_sched_loop
from lorad.utils.logger import get_logger, setdebug
from lorad.utils.utils import read_config, signal_stop, splash

logger = get_logger()

signal.signal(signal.SIGTERM, signal_stop)
signal.signal(signal.SIGINT, signal_stop)

splash()

logger.info("Loading config...")
config = read_config("config.json")

if "DEBUG" in config and config["DEBUG"]:
    setdebug()

carousel_providers = []

TEMPDIR = config["TEMPDIR"]

from lorad.stream.Streamer import Streamer
from lorad.music.yandex.YaMu import YaMu
from lorad.server.LoRadSrv import LoRadServer

yandex_music = YaMu(config["YAMU_TOKEN"], config["BITRATE_KBPS"])
carousel_providers.append(yandex_music)

logger.info("Starting LoRaD...")
server = ThreadingHTTPServer(("0.0.0.0", config["LISTEN_PORT"]), LoRadServer)
logger.info(f"Enabled features: {config['ENABLED_FEATURES']}")
streamer = Streamer(carousel_providers, server)

enabled_threads = [
    Thread(name="Streamer", target=streamer.carousel),
    Thread(name="HTTPServer", target=server.serve_forever)
]

if "NEURONEWS" in config["ENABLED_FEATURES"]:
    enabled_threads.append(Thread(name="NewsParser", target=parse_news))
    enabled_threads.append(Thread(name="Neuro", target=neurify_news))
    enabled_threads.append(Thread(name="ProgramMgr", target=prg_sched_loop))

# Sleeps are helping to avoid scrambled module startup logs
for athread in enabled_threads:
    athread.start()
    sleep(0.2)

logger.info("All threads started.")
streamer.start_carousel()

while True:
    for athread in enabled_threads:
        if not athread.is_alive:
            logger.error(f"A thread named [{athread.name}] died! Crashing!")
            os._exit(1)
    sleep(5)
