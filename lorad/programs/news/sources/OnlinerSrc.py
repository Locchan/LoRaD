from datetime import datetime
from time import mktime
import feedparser
import requests
from bs4 import BeautifulSoup
from lorad.programs.news.News import News
from lorad.programs.news.database.NewsDB import NewsDB
from lorad.programs.news.sources.GenericSrc import GenericSource
from lorad.utils.logger import get_logger

logger = get_logger()

# TODO: fix this shit
#  sometimes has ads for goods from the end of the news page
#  this wastes NN tokens!
class OnlinerSrc(GenericSource):
    rss_feeds = [
        "https://people.onliner.by/feed",
        "https://auto.onliner.by/feed",
        "https://money.onliner.by/feed",
        "https://tech.onliner.by/feed"
    ]
    name = "Онлайнер"

    def __init__(self, db_conn : NewsDB):
        self.db_conn = db_conn
        super().__init__(db_conn)
        self.rss_data = []
    
    def get_news(self) -> list[News]:
        return self._get_news_impl()

    def _get_news_impl(self):
        logger.info("Getting news from Onliner...")
        self.get_rss_data()
        self.get_news_text()
        news = []
        for anitem in self.rss_data:
            news.append(News(OnlinerSrc.name, anitem["title"], datetime.fromtimestamp(mktime(anitem["date"])), anitem["text"]))
        logger.info(f"Got {len(news)} news from Onliner.")
        return news

    def get_rss_data(self):
        for anrss in OnlinerSrc.rss_feeds:
            feed = feedparser.parse(anrss)

            if feed.status == 200:
                for entry in feed.entries:
                    # Creating a temporary News object to generate hash and check if this piece of news is already in the database
                    tmpnews = News(OnlinerSrc.name, entry.title, date_published=datetime.fromtimestamp(mktime(entry.published_parsed)))
                    if not self.db_conn.check_hash_exists(tmpnews.hash):
                        self.rss_data.append({
                            "title": entry.title,
                            "link": entry.link,
                            "date": entry.published_parsed
                        })
            else:
                logger.error("Failed to get RSS feed. Status code: ", feed.status)

    def get_news_text(self):
        for anrss in self.rss_data:
            response = requests.get(anrss["link"], headers=GenericSource.headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            news_raw = soup.find_all(class_='news-text')
            news_text = ""
            for anitem in news_raw:
                paragraphs = anitem.find_all("p")
                for aparagraph in paragraphs:
                    news_text += aparagraph.text + "\n"
            anrss["text"] = news_text
