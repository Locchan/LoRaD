from datetime import datetime
from time import mktime
import feedparser
from lorad.programs.news.News import News
from lorad.programs.news.database.NewsDB import NewsDB
from lorad.programs.news.sources.GenericSrc import GenericSource
from lorad.utils.logger import get_logger

logger = get_logger()

class MdzSrc(GenericSource):
    rss_feeds = [
        "https://meduza.io/rss/news",
    ]
    name = "Медуза"

    def __init__(self, db_conn : NewsDB):
        self.db_conn = db_conn
        super().__init__(db_conn)
        self.rss_data = []
    
    def get_news(self) -> list[News]:
        return self._get_news_impl()

    def _get_news_impl(self):
        logger.info("Getting news from Meduza...")
        self.get_rss_data()
        news = []
        for anitem in self.rss_data:
            news.append(News(MdzSrc.name, anitem["title"], datetime.fromtimestamp(mktime(anitem["date"])), anitem["text"], neurification_needed=False))
        logger.info(f"Got {len(news)} news from Meduza.")
        return news

    def get_rss_data(self):
        for anrss in MdzSrc.rss_feeds:
            feed = feedparser.parse(anrss)

            if feed.status == 200:
                for entry in feed.entries:
                    # Creating a temporary News object to generate hash and check if this piece of news is already in the database
                    tmpnews = News(MdzSrc.name, entry.title, date_published=datetime.fromtimestamp(mktime(entry.published_parsed)))
                    if not self.db_conn.check_hash_exists(tmpnews.hash):
                        self.rss_data.append({
                            "title": entry.title,
                            "link": entry.link,
                            "date": entry.published_parsed,
                            "text": self.sanitize_rss_text(entry.description)
                        })
            else:
                logger.error("Failed to get RSS feed. Status code: ", feed.status)

    def sanitize_rss_text(self, text_input):
        sanitized_text = text_input.replace("\xa0", " ").replace("<p>", "\n").replace("<\\p>", "\n")
        sanitized_text.strip()
        return sanitized_text