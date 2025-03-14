from time import sleep
from lorad.programs.news.database.NewsDB import NewsDB
from lorad.programs.news.sources.MeduzaSrc import MdzSrc
from lorad.programs.news.sources.OnlinerSrc import OnlinerSrc
from lorad.utils.utils import read_config

def parse_news():
    config = read_config()
    db = NewsDB(config["DBDIR"])
    while True:
        sources = [MdzSrc(db)]
        news = []
        for asource in sources:
            news = asource.get_news()
            db.add_news(news)
        sleep(config["NEWS_PARSER_PERIOD_MIN"] * 60)