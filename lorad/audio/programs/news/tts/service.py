import os

from lorad.audio.programs.news.orm import News
from lorad.audio.programs.news.tts.base import (
    TTSConfigurationError,
    TTSProviderError,
    TTSQuotaError,
)
from lorad.audio.programs.news.tts.factory import get_tts_provider
from lorad.common.utils.logger import get_logger
from lorad.common.utils.misc import read_config
from lorad.common.utils.shm import SHM_ROOT, is_shm_path, unlink_shm

logger = get_logger()


def _voice_dir(config):
    dirname = os.path.join(config.get("RUNTIME_MEDIA_DIR", SHM_ROOT), "neurovoice")
    if not is_shm_path(dirname):
        raise TTSConfigurationError("News TTS output must be inside /dev/shm/lorad.")
    return dirname


def _output_path(news_id, config):
    return os.path.join(_voice_dir(config), f"{news_id}.mp3")


def voice_news(news_id, provider=None) -> bool:
    config = read_config()
    logger.debug(f"Voicing news with configured TTS provider: {news_id}")
    partial_filename = None
    try:
        news = News.get_news_by_id(news_id)
        if news.body_prepared is None:
            logger.warning(f"News #{news_id} has no prepared text to voice.")
            return False

        selected_provider = provider or get_tts_provider(config)
        audio = selected_provider.synthesize_mp3(news.body_prepared)
        if not audio:
            raise TTSProviderError("TTS provider returned empty audio.")

        dirname = _voice_dir(config)
        os.makedirs(dirname, mode=0o700, exist_ok=True)
        output_filename = _output_path(news_id, config)
        partial_filename = output_filename + ".part"
        unlink_shm(partial_filename)
        with open(partial_filename, "wb") as out:
            out.write(audio)
        os.replace(partial_filename, output_filename)
        logger.info(
            f"Generated news audio with {selected_provider.name}: {output_filename}"
        )
        return True
    except TTSQuotaError as e:
        logger.warning(f"Could not voice news #{news_id}: {e}")
    except (TTSConfigurationError, TTSProviderError) as e:
        logger.error(f"Could not voice news #{news_id}: {e}")
    except Exception as e:
        logger.error(
            f"Unexpected error while voicing news #{news_id} [{e.__class__.__name__}]"
        )
        logger.exception(e)
    finally:
        if partial_filename is not None:
            unlink_shm(partial_filename)
    return False


def check_voiced(news_id) -> bool:
    config = read_config()
    try:
        return os.path.exists(_output_path(news_id, config))
    except TTSConfigurationError as e:
        logger.error(e)
        return False


def get_filelist(id_list) -> list[str]:
    config = read_config()
    reslist = []
    for news_id in id_list:
        try:
            filename = _output_path(news_id, config)
        except TTSConfigurationError as e:
            logger.error(e)
            break
        if os.path.exists(filename):
            reslist.append(filename)
        else:
            logger.warning(
                f"Was asked to give directions to file #{news_id} but it does not exist."
            )
            logger.warning("News will be inconsistent.")
    return reslist
