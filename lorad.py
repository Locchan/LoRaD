from http.server import ThreadingHTTPServer
from threading import Thread
from time import sleep
from lorad.newsagency.newsparser import parse_news
from lorad.utils.logger import get_logger
from lorad.utils.utils import read_config

logger = get_logger()

logger.info("Loading config...")
config = read_config("config.json")

connectors = []

TEMPDIR = config["TEMPDIR"]

from lorad.stream.Carousel import Carousel
from lorad.connectors.yandex.YaMu import YaMu
from lorad.server.LoRadSrv import LoRadServer


yandex_music = YaMu(config["YAMU_TOKEN"], config["BITRATE_KBPS"])
yandex_music.initialize()

connectors.append(yandex_music)

logger.info("Initializing server...")
server = ThreadingHTTPServer(("127.0.0.1", 8085), LoRadServer)

carousel = Carousel(connectors, server)

carousel_thread = Thread(name="Carousel", target=carousel.carousel)
carousel_thread.start()
carousel.start_carousel()

server_thread = Thread(name="HTTPServer", target=server.serve_forever)
server_thread.start()

news_parser_thread = Thread(name="NewsParser", target=parse_news)
news_parser_thread.start()

while True:
    if not carousel_thread.is_alive():
        logger.error("Carousel thread died! Restarting...")
        exit(1)
    if not server_thread.is_alive():
        logger.error("Server thread died! Restarting...")
        exit(1)
    if not news_parser_thread.is_alive():
        logger.error("News parser thread died! Restarting...")
        exit(1)
    sleep(5)