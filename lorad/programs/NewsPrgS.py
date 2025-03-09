import datetime
import os
import ffmpeg
from lorad.programs.GenericPrg import GenericPrg
from lorad.programs.news.database.NewsDB import NewsDB
from lorad.programs.news.neuro.neurovoice import check_voiced, get_filelist, voice_news
from lorad.utils.logger import get_logger
from lorad.utils.utils import read_config

logger = get_logger()

class NewsPrgS(GenericPrg):
    name = "NewsSmall"

    def __init__(self, start_times: datetime.time, preparation_needed_mins: int):
        super().__init__(start_times, NewsPrgS.name, preparation_needed_mins)
        self.config = read_config()
        self.db = NewsDB(self.config["DBDIR"])
        self.jingle_path = os.path.join(self.config["DATADIR"], "resources", self.config["ENABLED_PROGRAMS"][NewsPrgS.name]["jingle_path"])

    def _prepare_program_impl(self):
        news = self.db.get_unread_news()
        if len(news) == 0:
            logger.warning("No news!")
            return
        for anews in news:
            if not check_voiced(anews["hash"]):
                voice_news(anews["hash"])
        news_hashes = [x["hash"] for x in news]

        # TODO: Jingles by source (or news source name being clearly spoken at the end/start of the block)
        news_files = get_filelist(news_hashes)

        # Re-encode neuro files to 320kbps 44100 so that we don't change quality dramatically
        news_digest = self._reencode_news(news_files)
        logger.info("Program prepared")
        self.db.mark_as_read(news_hashes)
        return [news_digest]
    
    def _reencode_news(self, news_files):
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
        concatenated = ffmpeg.concat(*inputs, v=0, a=1).output(news_file, audio_bitrate='320k', ar=44100)
        ffmpeg.run(concatenated)
        return news_file