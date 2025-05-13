import datetime
import os
import ffmpeg
from lorad.radio.programs.GenericPrg import GenericPrg
from lorad.radio.programs.news.orm import News
from lorad.radio.programs.news.neuro.neurovoice import check_voiced, get_filelist, voice_news
from lorad.common.utils.logger import get_logger
from lorad.common.utils.utils import read_config

logger = get_logger()

class NewsPrgS(GenericPrg):
    name = "NewsSmall"

    def __init__(self, start_times: datetime.time, preparation_needed_mins: int):
        super().__init__(start_times, NewsPrgS.name, preparation_needed_mins)
        self.config = read_config()
        self.jingle_path = os.path.join(self.config["RESDIR"], self.config["ENABLED_PROGRAMS"][NewsPrgS.name]["jingle_path"])

    def _prepare_program_impl(self):
        news = News.get_news()
        if len(news) == 0:
            logger.warning("No news!")
            return
        for anews in news:
            if not check_voiced(anews.id):
                voice_news(anews.id)
        news_ids = [x.id for x in news]

        # TODO: Jingles by source (or news source name being clearly spoken at the end/start of the block)
        news_files = get_filelist(news_ids)

        # Re-encode neuro files to 320kbps 44100 so that we don't change quality dramatically
        news_digest = self._reencode_news(news_files)
        logger.info("Program prepared")
        News.mark_as_read(news_ids)
        return [news_digest]
    
    def _reencode_news(self, news_files) -> str:
        reencode_date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        digestdir = os.path.join(self.config["DATADIR"], "neurovoice", "digests")
        if not os.path.exists(digestdir):
            os.makedirs(digestdir)
        news_file = os.path.join(digestdir, "news_digest_" + reencode_date + ".mp3")
        tempfiles = [self.jingle_path]
        logger.info("Reencoding news...")
        for afile in news_files:
            tmpfilename = afile + reencode_date + ".mp3"
            tempfiles.append(tmpfilename)
            ffmpeg.input(afile).output(tmpfilename, audio_bitrate='320k', ar=44100, acodec='libmp3lame', loglevel="quiet", ac=2, af="apad=pad_dur=2").run(overwrite_output=True)
        logger.info("Concatenating news files into a digest")
        inputs = [ffmpeg.input(f) for f in tempfiles]
        concatenated = ffmpeg.concat(*inputs, v=0, a=1).output(news_file, audio_bitrate='320k', ar=44100, loglevel="quiet")
        ffmpeg.run(concatenated)
        return news_file