from datetime import datetime
from time import mktime
import feedparser
from lorad.audio.programs.news.orm.News import News
from lorad.audio.programs.news.sources.GenericSrc import GenericSource
from lorad.common.utils.logger import get_logger

logger = get_logger()

class MdzSrc(GenericSource):
    rss_feeds = [
        "https://meduza.io/rss/news",
    ]
    name = "Медуза"

    def __init__(self):
        self.name = MdzSrc.name
        super().__init__()
        self.rss_data = []

    def parse_news(self) -> list[News]:
        return self._parse_news_impl()

    def _parse_news_impl(self):
        logger.info(f"Parsing news from {self.name}...")
        self.get_rss_data()
        news = []
        for anitem in self.rss_data:
            news_obj = News()
            news_obj.source = MdzSrc.name
            news_obj.title = anitem["title"]
            news_obj.body_raw = anitem["text"]
            news_obj.date_published = datetime.fromtimestamp(mktime(anitem["date"]))
            news_obj.preparation_needed = False
            news.append(news_obj)
        return news

    def get_rss_data(self):
        for anrss in MdzSrc.rss_feeds:
            feed = feedparser.parse(anrss)

            if feed.status == 200:
                for entry in feed.entries:
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