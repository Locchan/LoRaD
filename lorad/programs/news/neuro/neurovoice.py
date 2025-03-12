import os
from google.cloud import texttospeech
from lorad.programs.news.database.NewsDB import NewsDB
from lorad.utils.logger import get_logger
from lorad.utils.utils import read_config

logger = get_logger()

def voice_news(news_hash):
    config = read_config()
    db = NewsDB(config["DBDIR"])
    logger.debug(f"Voicing news: {news_hash}")
    try:
        news = db.get_news_by_hash(news_hash)
        if news[0]["body_prepared"] is None:
            return
        client = texttospeech.TextToSpeechClient.from_service_account_info(config["GOOGLE_CLOUD_API_USERDATA"])
        input_text = texttospeech.SynthesisInput(text=news[0]["body_prepared"])

        voice = texttospeech.VoiceSelectionParams(
            language_code="ru-RU",
            name="ru-RU-Standard-B",
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        response = client.synthesize_speech(
            input=input_text,
            voice=voice,
            audio_config=audio_config
        )
        dirname = os.path.join(config["DATADIR"], "neurovoice")
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        output_filename = os.path.join(dirname, f"{news_hash}.mp3")

        with open(output_filename, "wb") as out:
            out.write(response.audio_content)
            logger.debug(f"Generated news audio: {output_filename}")
    except Exception as e:
        logger.error("Error while voicing news [{}]: ", e.__class__.__name__)
    
def check_voiced(ahash) -> bool:
    config = read_config()
    return os.path.exists(os.path.join(config["DATADIR"], "neurovoice", f"{ahash}.mp3"))

def get_filelist(hashlist) -> list[str]:
    config = read_config()
    reslist = []
    for ahash in hashlist:
        filename = os.path.join(config["DATADIR"], "neurovoice", f"{ahash}.mp3")
        if os.path.exists(filename):
            reslist.append(filename)
        else:
            logger.warning(f"Was asked to give directions to {ahash} but it does not exist.")
            logger.warning(f"News will be inconsistent.")
    return reslist