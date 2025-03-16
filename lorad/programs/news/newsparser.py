from time import sleep
from lorad.programs.news.orm import News
from lorad.programs.news.sources.MeduzaSrc import MdzSrc
from lorad.utils.logger import get_logger
from lorad.utils.utils import read_config

logger = get_logger()

def parse_news():
    config = read_config()
    while True:
        sources = [MdzSrc()]
        news = []
        for asource in sources:
            news = asource.parse_news()
            news_added = News.add_news(news)
            logger.info(f"Added {news_added} news from {asource.name}.")
        sleep(config["NEWS_PARSER_PERIOD_MIN"] * 60)