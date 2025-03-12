from datetime import datetime
from hashlib import sha256


class News():
    def __init__(self, source, title, date_published, body=None, neurification_needed=True):
        self.source : str = source
        self.title : str = title
        self.body_unprepared : str = body
        self.date_published : datetime = date_published
        self.neurification_needed = neurification_needed
        hash = sha256(f"{self.source}{self.title}{self.date_published}".encode("utf-8"))
        self.hash = hash.hexdigest()