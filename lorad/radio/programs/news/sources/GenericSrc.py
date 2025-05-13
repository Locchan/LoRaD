from lorad.radio.programs.news.orm.News import News


class GenericSource():

    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36'}

    def __init__(self):
        pass

    def parse_news(self) -> list[News]:
        pass