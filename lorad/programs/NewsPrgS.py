import datetime
import os
import shutil

import ffmpeg
from lorad.programs.GenericPrg import GenericPrg
from lorad.programs.news.neuro.neuronews import get_most_important_news_by_source
from lorad.programs.news.neuro.neurovoice import check_voiced, get_filelist, voice_news
from lorad.utils.logger import get_logger
from mutagen.mp3 import MP3

logger = get_logger()

class NewsPrgS(GenericPrg):
    name = "NewsSmall"

    # Strict naming! Check programs.news.sources.*.name
    news_per_source = {
        "Онлайнер": 5
    }

    def __init__(self, start_times: datetime.time, jingle_path: str, preparation_needed_mins: int):
        super().__init__(start_times, jingle_path, NewsPrgS.name, preparation_needed_mins)

    def _prepare_program_impl(self):
        news_to_prepare = {}
        for asource in NewsPrgS.news_per_source:
            news_to_prepare[asource] = get_most_important_news_by_source(asource, 20, 5)
        for asource in news_to_prepare:
            for ahash in news_to_prepare[asource]:
                if not check_voiced(ahash):
                    voice_news(ahash)
        # TODO: Jingles by source (or news source name being clearly spoken at the end/start of the block)
        total_news_list = []
        for asource in news_to_prepare:
            total_news_list.extend(news_to_prepare[asource])
        news_files = get_filelist(total_news_list)

        # Re-encode neuro files to 320kbps 44100 so that we don't change quality dramatically
        self._reencode_news(news_files)
        logger.info("Program prepared")
        return news_files
    
    def _reencode_news(self, news_files):
        for afile in news_files:
            track_info = MP3(afile).info
            if int(track_info.bitrate / 1000) != 320 or True:
                logger.info(f"Re-encoding {afile} to 320kbps 44100...")
                tmpfilename = afile + "rnc.mp3"
                ffmpeg.input(afile).output(tmpfilename, audio_bitrate='320k', ar=44100, acodec='libmp3lame', loglevel="quiet", ac=2).run(overwrite_output=True)
                os.remove(afile)
                shutil.move(tmpfilename, afile)
        pass