import os
from google.api_core.exceptions import ResourceExhausted
from google.cloud import texttospeech
from lorad.audio.programs.news.orm import News
from lorad.common.utils.logger import get_logger
from lorad.common.utils.misc import read_config

logger = get_logger()

def voice_news(news_id):
    config = read_config()
    logger.debug(f"Voicing news: {news_id}")
    try:
        news = News.get_news_by_id(news_id)
        if news.body_prepared is None:
            return
        client = texttospeech.TextToSpeechClient.from_service_account_info(config["GOOGLE_CLOUD_API_USERDATA"])
        input_text = texttospeech.SynthesisInput(text=news.body_prepared)

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
        output_filename = os.path.join(dirname, f"{news_id}.mp3")

        with open(output_filename, "wb") as out:
            out.write(response.audio_content)
            logger.debug(f"Generated news audio: {output_filename}")
    except ResourceExhausted:
        logger.warn(f"Reached resource limit when trying to voice a piece of news.")
    except Exception as e:
        logger.error(f"Error while voicing news [{e.__class__.__name__}]: {e}")



def check_voiced(anid) -> bool:
    config = read_config()
    return os.path.exists(os.path.join(config["DATADIR"], "neurovoice", f"{anid}.mp3"))


def get_filelist(id_list) -> list[str]:
    config = read_config()
    reslist = []
    for anid in id_list:
        filename = os.path.join(config["DATADIR"], "neurovoice", f"{anid}.mp3")
        if os.path.exists(filename):
            reslist.append(filename)
        else:
            logger.warning(f"Was asked to give directions to file #{anid} but it does not exist.")
            logger.warning("News will be inconsistent.")
    return reslist