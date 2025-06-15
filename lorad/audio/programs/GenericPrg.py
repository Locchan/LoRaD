import datetime
import os

import lorad.common.utils.globs as globs
from lorad.common.utils.logger import get_logger

logger = get_logger()

class GenericPrg():
    def __init__(self, start_times: list[datetime.time], name: str, name_pretty: str, preparation_needed_mins: int):
        self.name_pretty = name_pretty
        self.name = name
        self.start_times  = start_times
        self.preparation_needed_mins = preparation_needed_mins
        self.prepared_program = None
        self.preparations_started = False
        self.program_running = False

    def prepare_program(self):
        self.preparations_started = True
        logger.info(f"Starting to prepare program: {self.name}.")
        logger.info(f"Program will start in {self.preparation_needed_mins} minutes.")
        self.prepared_program = self._prepare_program_impl() 
    
    # Should return {"track_name": "track_filepath", ...}
    def _prepare_program_impl(self) -> dict:
        return {} #dummy

    def start_program(self):
        if self.prepared_program is None:
            logger.error(f"Can't run program [{self.name}]: not prepared!")
            self.preparations_started = False
            return
        try:
            self.program_running = True
            for aname, afile in self.prepared_program.items():
                if not os.path.exists(afile):
                    logger.error(f"Can't run program [{self.name}]: file [{afile}] does not exist!")
                    return
            logger.info(f"Running a scheduled program: [{self.name}]...")
            globs.RADIO_STREAMER.stop_carousel()
            for anum, afile in enumerate(self.prepared_program):
                logger.info(f"Program: {self.name}; Track {anum+1}/{len(self.prepared_program)}")
                globs.RADIO_STREAMER.serve_file(afile, track_name=aname)
            logger.info(f"Program [{self.name}] finished. Restarting carousel.")
        except Exception as e:
            logger.error(f"Failed to run the program: {e.__class__.__name__}")
            logger.info("Falling back to the carousel")
        finally:
            globs.RADIO_STREAMER.start_carousel()
            self.prepared_program = None
            self.preparations_started = False
            self.program_running = False
