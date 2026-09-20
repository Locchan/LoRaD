import datetime
import os

from lorad.audio.hub import get_hub
from lorad.audio.ramfile import DoubleBuffer, file_duration_s
from lorad.api.utils.misc import forbid_switching
import lorad.common.utils.globs as globs
from lorad.common.utils.logger import get_logger
from lorad.common.utils.misc import read_config
from lorad.common.utils.shm import pause_cleanup, resume_cleanup, unlink_shm

logger = get_logger()


class GenericPrg:
    def __init__(self, start_times: list[datetime.time], name: str, name_pretty: str, preparation_needed_mins: int):
        self.name_pretty = name_pretty
        self.name = name
        self.name_tech = f"program_{name}"
        self.start_times = start_times
        self.preparation_needed_mins = preparation_needed_mins
        self.prepared_program = None
        self.preparations_started = False
        self.program_running = False

    def prepare_program(self):
        self.preparations_started = True
        logger.info(f"Starting to prepare program: {self.name}.")
        logger.info(f"Program will start in {self.preparation_needed_mins} minutes.")
        # Nothing in shm may be collected from here until the program is done with it.
        pause_cleanup(self.name, hold_s=self.preparation_needed_mins * 60 * 3)
        try:
            self.prepared_program = self._prepare_program_impl()
        except Exception:
            resume_cleanup()
            raise
        if not self.prepared_program:
            resume_cleanup()

    def _prepare_program_impl(self) -> dict:
        return {}

    def start_program(self):
        player_before_program = globs.CURRENT_PLAYER_NAME
        if self.prepared_program is None:
            logger.error(f"Can't run program [{self.name}]: not prepared!")
            self.preparations_started = False
            resume_cleanup()
            return
        hub = get_hub()
        buffers = DoubleBuffer()
        config = read_config()
        feed_chunk = config["CHUNK_SIZE_KB"] * 1024
        prev = None
        if player_before_program:
            for aplayer in globs.PLAYERS:
                if aplayer.name_tech == player_before_program:
                    prev = aplayer
                    break
        acquired = False
        try:
            self.program_running = True
            total = 0.0
            for aname, afile in self.prepared_program.items():
                if not os.path.exists(afile):
                    logger.error(f"Can't run program [{self.name}]: file [{afile}] does not exist!")
                    return
                total += file_duration_s(afile)
            if total > 0:
                forbid_switching(int(total) + 1)
            logger.info(f"Running a scheduled program: [{self.name}]...")
            hub.acquire(self)
            acquired = True
            for anum, (aname, afile) in enumerate(self.prepared_program.items()):
                logger.info(f"Program: {self.name}; Track {anum+1}/{len(self.prepared_program)}")
                if prev is not None:
                    prev.currently_playing = aname
                buffers.load_current_track(afile, aname)
                hub.begin_source(self, "mp3", bitrate_kbps=buffers.current.bitrate_kbps)
                while buffers.current.ready and self.program_running:
                    pos = 0
                    data = buffers.current.data
                    while pos < len(data) and self.program_running:
                        chunk = data[pos : pos + feed_chunk]
                        if not hub.feed(self, chunk):
                            break
                        pos += len(chunk)
                    if buffers.current.is_last_window():
                        break
                    if not buffers.wait_preload(timeout=30):
                        raise RuntimeError(f"Timed out loading program file: {afile}")
                    buffers.swap()
            logger.info(f"Program [{self.name}] finished.")
        except Exception as e:
            logger.error(f"Failed to run the program: {e.__class__.__name__}")
            logger.info("Falling back to the carousel")
            logger.exception(e)
        finally:
            if acquired:
                hub.release(self)
                if prev is not None:
                    prev.start()
                    hub.acquire(prev)
            if self.prepared_program:
                for afile in self.prepared_program.values():
                    unlink_shm(afile)
            self.prepared_program = None
            self.preparations_started = False
            self.program_running = False
            resume_cleanup()
