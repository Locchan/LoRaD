import re
from time import sleep
from lorad.programs.news.database.NewsDB import NewsDB
from lorad.programs.news.sources.OnlinerSrc import OnlinerSrc
from lorad.utils.logger import get_logger
from lorad.utils.utils import read_config
from openai import OpenAI

logger = get_logger()

def get_summary(openai_api_key, body_full):
    client = OpenAI(
        api_key=openai_api_key,
    )

    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "Веди себя как диктор на радио, зачитывающий новости."
            },
            {
                "role": "user",
                "content": f"Перескажи эту новость кратко без информации про телеграм бота и какой-либо рекламы: \n{body_full}",
            }
        ],
        model="gpt-4o-mini"
    )
    return chat_completion.choices[0].message.content

def neurify_news():
    config = read_config()
    db = NewsDB(config["DBDIR"])
    logger.info("NeuroNews started...")
    while True:
        logger.info("Neurifying news...")
        nn_news = db.get_non_neurified_news()
        success = 0
        for anews in nn_news:
            try:
                summary = get_summary(config["OPENAI_API_KEY"], anews["body_raw"])
                db.add_neuro_to_existing(anews["hash"], summary)
                success += 1
            except Exception as e:
                logger.error(f"Could not neurify a piece of news: {e.__class__.__name__}")
        logger.info(f"Neurified {success} news objects.")
        sleep(config["NEWS_NEURIFIER_PERIOD_MIN"] * 60)

def get_most_important_news_by_source(source: str, titles_to_give: int, important_to_ask: int) -> list[str]:
    config = read_config()
    db = NewsDB(config["DBDIR"])
    neurified_news = db.get_neurified_news_by_source(source, titles_to_give)
    titles = []
    for anitem in neurified_news:
        titles.append(anitem["title"])
    prompt = f"Выбери наиболее важные {important_to_ask} штук новостей из следующих заголовков. Ответь только их номерами через запятую.\n\n"
    for anumber, atitle in enumerate(titles):
        prompt += f"\n{anumber}: {atitle}"

    client = OpenAI(
        api_key=config["OPENAI_API_KEY"],
    )

    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model="gpt-4o-mini"
    )
    chat_response = chat_completion.choices[0].message.content
    filtered_response = filter_text(chat_response)
    important_idx = [int(x) - 1 for x in filtered_response.split(",")]
    important_hashes = [neurified_news[idx]["hash"] for idx in important_idx]
    return important_hashes 

# Removing all text, leaving only numbers and punctuation.
#  NN is stoopid, sometimes answers with words even when clearly instructed not to do so.
def filter_text(text):
    return re.sub(r'[^\d\W]', '', text)
