import os
import sqlite3

from lorad.newsagency.News import News
from lorad.utils.logger import get_logger

logger = get_logger()

class NewsDB():

    def __init__(self, db_dir):
        self.db_dir = db_dir
        self.connection = self.initialize()

    def initialize(self) -> sqlite3.Connection:
        db_needs_initializing = False
        db_path_full = os.path.join(self.db_dir, "newsdb.sqlite")
        if not os.path.exists(db_path_full):
            db_needs_initializing = True
        connection = sqlite3.connect(db_path_full)
        if db_needs_initializing:
            logger.info("Initializing NewsDB...")
            cursor = connection.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY,
                hash TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                body_raw TEXT NOT NULL,
                body_neuro TEXT,
                date_published DATETIME,
                used BOOLEAN
                );
                ''')
            cursor.close()
            logger.info("NewsDB initialized.")
        return connection
    
    def add_news(self, news : list[News]):
        logger.debug(f"Adding {len(news)} news...")
        for anews in news:
            cursor = self.connection.cursor()
            cursor.execute('INSERT OR IGNORE INTO news (hash, title, body_raw, date_published) VALUES (?, ?, ?, ?)',
                            (anews.hash, anews.title, anews.body_unprepared, anews.date_published))
        self.connection.commit()
    
    def add_neuro_to_existing(self, hash, neuro_body):
        cursor = self.connection.cursor()
        cursor.execute('UPDATE news SET body_neuro = ? where hash = ?',(neuro_body, hash))
        self.connection.commit()

    def check_hash_exists(self, hash) -> bool:
        cursor = self.connection.cursor()
        cursor.execute(f'SELECT * FROM news WHERE hash="{hash}"')
        data = cursor.fetchall()
        return len(data) != 0

