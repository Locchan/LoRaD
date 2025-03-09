#!/usr/bin/env python3

from http.server import ThreadingHTTPServer
import os
from threading import Thread
from time import sleep
from lorad.programs.news.neuro.neuronews import neurify_news
from lorad.programs.news.newsparser import parse_news
from lorad.programs.program_mgr import prg_sched_loop
from lorad.utils.logger import get_logger
from lorad.utils.utils import read_config, splash

logger = get_logger()

splash()

logger.info("Loading config...")
config = read_config("config.json")

carousel_providers = []

TEMPDIR = config["TEMPDIR"]

from lorad.stream.Streamer import Streamer
from lorad.music.yandex.YaMu import YaMu
from lorad.server.LoRadSrv import LoRadServer

yandex_music = YaMu(config["YAMU_TOKEN"], config["BITRATE_KBPS"])
yandex_music.initialize()

carousel_providers.append(yandex_music)

logger.info("Starting LoRaD...")
server = ThreadingHTTPServer(("0.0.0.0", 8085), LoRadServer)

streamer = Streamer(carousel_providers, server)
streamer_thread = Thread(name="Streamer", target=streamer.carousel)
server_thread = Thread(name="HTTPServer", target=server.serve_forever)
news_parser_thread = Thread(name="NewsParser", target=parse_news)
neuro_thread = Thread(name="Neuro", target=neurify_news)
program_thread = Thread(name="ProgramMgr", target=prg_sched_loop)

# Sleeps are helping to avoid scrambled module startup logs
streamer_thread.start()
sleep(0.2)
server_thread.start()
sleep(0.2)
program_thread.start()
sleep(0.2)
news_parser_thread.start()
sleep(0.2)
neuro_thread.start()
sleep(0.2)

logger.info("All threads started.")
streamer.start_carousel()

while True:
    if not streamer_thread.is_alive():
        logger.error("Carousel thread died! Restarting...")
        os._exit(1)
    if not server_thread.is_alive():
        logger.error("Server thread died! Restarting...")
        os._exit(1)
    if not news_parser_thread.is_alive():
        logger.error("News parser thread died! Restarting...")
        os._exit(1)
    if not neuro_thread.is_alive():
        logger.error("Neuro thread died! Restarting...")
        os._exit(1)
    if not program_thread.is_alive():
        logger.error("Program manager thread died! Restarting...")
        os._exit(1)
    sleep(5)
