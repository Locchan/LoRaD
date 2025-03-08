from time import sleep
from lorad.newsagency.database.NewsDB import NewsDB
from lorad.newsagency.sources.OnlinerSrc import OnlinerSource
from lorad.utils.utils import read_config

def neurify_news():
    config = read_config()
    db = NewsDB(config["DBDIR"])
    while True:
        sources = [OnlinerSource(db)]
        news = []
        for asource in sources:
            news = asource.get_news()
        db.add_news(news)
        sleep(config["NEWS_NEURIFIER_PERIOD_MIN"] * 60)