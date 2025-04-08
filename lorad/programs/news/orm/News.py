import datetime
from typing import Tuple
from sqlalchemy import Result, String, Text, UniqueConstraint, select, desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from lorad.database.Base import Base
from lorad.database.MySQL import MySQL



class News(Base):
    __tablename__ = "news"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    body_raw: Mapped[str] = mapped_column(Text, nullable=False)
    body_prepared: Mapped[str] = mapped_column(Text, nullable=True)
    date_published: Mapped[datetime.datetime] = mapped_column(nullable=False)
    preparation_needed: Mapped[bool] = mapped_column(default=False)
    used: Mapped[bool] = mapped_column(default=False)

    __table_args__ = (UniqueConstraint("source", "title", "date_published", name="src_ttl_date_unx"),)


def add_news(news: list[News]) -> int:
    news_added = 0
    with MySQL.get_session() as session:
        for anitem in news:
            if not anitem.preparation_needed and anitem.body_prepared is None:
                anitem.body_prepared = anitem.body_raw
                prettify_text(anitem)
            try:
                session.add(anitem)
                session.commit()
                news_added += 1
            # IntegrityError gets thrown when we're trying to add duplicate news.
            except IntegrityError:
                session.rollback()
    return news_added


def prettify_text(newsobj: News):
    newsobj.body_raw = newsobj.body_raw.replace('\xa0', ' ')
    newsobj.body_raw = newsobj.body_prepared.strip()
    newsobj.title = newsobj.title.replace('\xa0', ' ')
    newsobj.title = newsobj.title.strip()
    if newsobj.body_prepared is not None:
        newsobj.body_prepared = newsobj.body_prepared.replace('\xa0', ' ')
        newsobj.body_prepared = newsobj.body_prepared.strip()


def get_news_by_id(news_id):
    with MySQL.get_session() as session:
        return session.scalar(select(News).where(News.id == news_id))


def add_prepared_body_to_existing(news_id, body_prepared) -> None:
    with MySQL.get_session() as session:
        news_obj: News = session.scalar(select(News).where(News.id == news_id))
        news_obj.body_prepared = body_prepared
        session.commit()


def get_unprepared_news() -> Result[Tuple[News]]:
    with MySQL.get_session() as session:
        return session.scalars(select(News).where(News.body_prepared is None and News.used == False)).all()


def get_prepared_news_by_src(source) -> Result[Tuple[News]]:
    with MySQL.get_session() as session:
        return session.scalars(select(News).where(News.body_prepared is not None and News.source == source)).all()

def get_news(news_to_get: int = 10) -> Result[Tuple[News]]:
    with MySQL.get_session() as session:
        return session.scalars(select(News).order_by(desc(News.date_published)).limit(news_to_get)).all()

def mark_as_read(ids) -> None:
    with MySQL.get_session() as session:
        news = session.scalars(select(News).filter(News.id.in_(ids))).all()
        for anews in news:
            anews.used = True
        session.commit()
