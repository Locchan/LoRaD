import datetime
import os

from lorad.utils.logger import get_logger
from lorad.utils.utils import read_config

logger = get_logger()

class GenericPrg():
    def __init__(self, start_times: list[datetime.time], name: str, preparation_needed_mins: int):
        config = read_config()
        self.name = name
        self.start_times  = start_times
        self.preparation_needed_mins = preparation_needed_mins
        self.prepared_program = None
        self.preparations_started = False
        self.program_running = False

    def prepare_program(self):
        logger.info(f"Starting to prepare program: {self.name}.")
        logger.info(f"Program will start in {self.preparation_needed_mins} minutes.")
        self.preparations_started = True
        self.prepared_program = self._prepare_program_impl() 
    
    def _prepare_program_impl(self):
        pass

    def start_program(self):
        if self.prepared_program is None:
            logger.error(f"Can't run program [{self.name}]: not prepared!")
            return
        try:
            from __main__ import streamer
            self.program_running = True
            for aprogram in self.prepared_program:
                if not os.path.exists(aprogram):
                    logger.error(f"Can't run program [{self.name}]: file [{aprogram}] does not exist!")
                    return
            logger.info(f"Running a scheduled program: [{self.name}]...")
            streamer.stop_carousel()
            for anum, afile in enumerate(self.prepared_program):
                logger.info(f"Program: {self.name}; Track {anum+1}/{len(self.prepared_program)}")
                streamer.serve_file(afile)
            logger.info(f"Program [{self.name}] finished. Restarting carousel.")
        except Exception as e:
            logger.error(f"Failed to run the program: {e.__class__.__name__}")
            logger.info("Falling back to the carousel")
        finally:
            streamer.start_carousel()
            self.prepared_program = None
            self.preparations_started = False
            self.program_running = False
