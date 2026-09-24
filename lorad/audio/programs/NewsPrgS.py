import datetime
import os
import random
from sqlalchemy.exc import IntegrityError
from lorad.audio.programs.GenericPrg import GenericPrg
from lorad.audio.programs.news.orm import News
from lorad.audio.programs.news.tts.service import check_voiced, get_filelist, voice_news
from lorad.audio.utils.ffmpeg_utils import ffmpeg_concatenate, ffmpeg_reencode
from lorad.common.database.MySQL import MySQL
from lorad.common.utils.globs import FEAT_NEWS_ADS, FEAT_NEWS_RANDOM_FILE
from lorad.common.utils.logger import get_logger
from lorad.common.utils.misc import read_config, feature_enabled
from lorad.common.utils.shm import PINNED_DATA, PINNED_RES, SHM_ROOT, pinned_path

logger = get_logger()

def generate_fake_news(news):
    from lorad.audio.programs.news.neuro.neuronews import fakeify_news
    fake_news = 0
    for anitem in news:
        if anitem.fake:
            fake_news+=1
    if fake_news == 2:
        logger.info("No need to generate fake news.")
        return news
    logger.info("Generating fake news...")
    if len(news) < 2:
        logger.warn("Not enough news to generate fake items; skipping.")
        return news
    news_to_fake = random.sample(news, 2)
    config = read_config()
    openai_api_key = config["OPENAI_API_KEY"]
    for anitem in news_to_fake:
        news.remove(anitem)
    try:
        fake_text = fakeify_news(openai_api_key, [x.body_prepared for x in news_to_fake if x.body_prepared])
    except Exception:
        news.extend(news_to_fake)
        raise
    if len(fake_text) < len(news_to_fake):
        logger.warn("Fake news model returned fewer jokes than requested; skipping.")
        news.extend(news_to_fake)
        return news
    news_to_fake_filtered = []
    for iter, anewstofake in enumerate(news_to_fake):
        news_to_fake_filtered.append(
            News.News(
                source = anewstofake.source,
                title = anewstofake.title,
                body_raw = anewstofake.body_raw,
                body_prepared = fake_text[iter],
                date_published = datetime.datetime.fromtimestamp(1),
                preparation_needed = anewstofake.preparation_needed,
                fake = True,
                used = anewstofake.used
            )
        )
    logger.info(f"Generated {len(news_to_fake_filtered)} fake news.")
    with MySQL.get_session() as session:
        for anitem in news_to_fake_filtered:
            try:
                session.add(anitem)
                session.commit()
                session.refresh(anitem)
                news.append(anitem)
            except IntegrityError:
                session.rollback()
                news_to_fake_filtered.remove(anitem)
    return news

class NewsPrgS(GenericPrg):
    name = "NewsSmall"
    name_pretty = "Panorama"

    def __init__(self, start_times: datetime.time, preparation_needed_mins: int):
        super().__init__(start_times, NewsPrgS.name, NewsPrgS.name_pretty, preparation_needed_mins)
        self.config = read_config()
        # Assets play from the shm copies made at boot; the config points at the on-disk originals.
        self.jingle_path = pinned_path(PINNED_RES, self.config["ENABLED_PROGRAMS"][NewsPrgS.name]["jingle_path"])
        if not os.path.exists(self.jingle_path):
            logger.warning(f"Jingle not found: {self.jingle_path}")

    def _prepare_program_impl(self):
        news = News.get_news()
        if len(news) == 0:
            logger.warning("No news!")
            return
        random.shuffle(news)
        for anews in news:
            if not check_voiced(anews.id):
                voice_news(anews.id)
        news_ids = [x.id for x in news]

        # TODO: Jingles by source (or news source name being clearly spoken at the end/start of the block)
        news_files = get_filelist(news_ids)

        # Re-encode neuro files to self.config["BITRATE_KBPS"] and 44100 sample rate so that we don't change the stream dramatically
        news_digest_filepath = self._reencode_news(news_files)
        logger.info("Program prepared")
        News.mark_as_read(news_ids)
        news_name = f"{self.name_pretty}: {(datetime.datetime.now() + datetime.timedelta(hours=1)).strftime('%Y-%m-%d %H')}"
        return {news_name: news_digest_filepath}
    
    def _reencode_news(self, news_files) -> str:
        reencode_date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        digestdir = os.path.join(
            self.config.get("RUNTIME_MEDIA_DIR", SHM_ROOT), "neurovoice", "digests"
        )
        if not os.path.exists(digestdir):
            os.makedirs(digestdir)
        news_file = os.path.join(digestdir, "news_digest_" + reencode_date + ".mp3")
        tempfiles = [self.jingle_path]
        logger.info("Reencoding news...")
        for afile in news_files:
            tmpfilename = afile[:-4] + "_reenc" + ".mp3"
            tempfiles.append(tmpfilename)
            if not os.path.exists(tmpfilename):
                ffmpeg_reencode(afile, ["-b:a", f"{self.config['BITRATE_KBPS']}k", "-c:a", "libmp3lame", "-ar", "44100", "-ac", "2", "-af", "apad=pad_dur=2"], tmpfilename)
        logger.info("Concatenating news files into a digest")
        if feature_enabled(FEAT_NEWS_ADS):
            tempfiles = self.add_ads(tempfiles)
        if feature_enabled(FEAT_NEWS_RANDOM_FILE):
            tempfiles = self.add_random_files(tempfiles)
        logger.debug("Will use the following files:")
        logger.debug(tempfiles)
        ffmpeg_concatenate(tempfiles, news_file, artist="NeuroNews", title=f"Новости за {datetime.datetime.now().strftime('%Y-%m-%d %H')}")
        # Voice files stay so the same headlines are not voiced again; the shm janitor
        # trims the oldest ones once shm fills up.
        return news_file

    def add_random_files(self, files_list, count=1):
        random_filesdir = pinned_path(PINNED_DATA, "resources", "random_voices")
        rnd_files = [os.path.join(random_filesdir, f) for f in os.listdir(random_filesdir) if os.path.isfile(os.path.join(random_filesdir, f)) and f != ".gitkeep"]
        logger.info(f"Adding {count} random files to the news of {len(rnd_files)} files total")
        if not rnd_files:
            logger.warning("Could not get a random file to add to the news.")
            return files_list
        random_files_to_add = random.sample(rnd_files, count)
        if not isinstance(random_files_to_add, list):
            random_files_to_add = [random_files_to_add]
        files_list.extend(random_files_to_add)
        return files_list

    def add_ads(self, files_list, count=1):
        adsdir = pinned_path(PINNED_DATA, "resources", "ads")
        ad_files = [os.path.join(adsdir, f) for f in os.listdir(adsdir) if os.path.isfile(os.path.join(adsdir, f)) and f != ".gitkeep"]
        logger.info(f"Adding {count} ads to the news of {len(ad_files)} ads total")
        if not ad_files:
            logger.warning("Could not get an ad to add to the news.")
            return files_list
        ads_to_add = random.sample(ad_files, count)
        if not isinstance(ads_to_add, list):
            ads_to_add = [ads_to_add]
        files_list.extend(ads_to_add)
        return files_list
