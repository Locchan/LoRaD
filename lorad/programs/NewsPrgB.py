import datetime
import ffmpeg
from lorad.programs.GenericPrg import GenericPrg
from lorad.programs.news.neuro.neuronews import get_most_important_news_by_source
from lorad.programs.news.neuro.neurovoice import check_voiced, get_filelist, voice_news
from lorad.utils.logger import get_logger

logger = get_logger()

class NewsPrgS(GenericPrg):
    name = "NewsSmall"

    # Strict naming! Check programs.news.sources.*.name
    news_per_source = {
        "Онлайнер": 3,
        "Медуза": 7
    }

    def __init__(self, start_times: datetime.time, preparation_needed_mins: int):
        super().__init__(start_times, NewsPrgS.name, preparation_needed_mins)

    def _prepare_program_impl(self):
        news_to_prepare = {}
        for asource in NewsPrgS.news_per_source:
            news_to_prepare[asource] = get_most_important_news_by_source(asource, 20, NewsPrgS.news_per_source[asource])
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
        reencode_date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        news_file = "news_digest_" + reencode_date + ".mp3"
        tempfiles = []
        logger.info("Reencoding news...")
        for afile in news_files:
            tmpfilename = afile + reencode_date + ".mp3"
            tempfiles.append(tmpfilename)
            ffmpeg.input(afile).output(tmpfilename, audio_bitrate='320k', ar=44100, acodec='libmp3lame', loglevel="quiet", ac=2, af="apad=pad_dur=1.5").run(overwrite_output=True)
        logger.info("Concatenating news files into a digest")
        inputs = [ffmpeg.input(f) for f in tempfiles]
        concatenated = ffmpeg.concat(*inputs, v=0, a=1).output(news_file, loglevel="quiet")
        ffmpeg.run(concatenated)
        return [news_file]