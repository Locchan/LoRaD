import datetime
from threading import Thread
from time import sleep
from lorad.programs.GenericPrg import GenericPrg
from lorad.programs.NewsPrgS import NewsPrgS
from lorad.utils.logger import get_logger
from lorad.utils.utils import read_config

AVAILABLE_PROGRAMS: list[GenericPrg] = [NewsPrgS]
ENABLED_PROGRAMS: list[GenericPrg] = []
logger = get_logger()

def register_programs():
    logger.info("Registering programs...")
    config = read_config()
    for aprogram in AVAILABLE_PROGRAMS:
        if aprogram.name in config["ENABLED_PROGRAMS"]:
            logger.info(f"Enabling program: {aprogram.name}")
            try:
                dates = []
                for anitem in config["ENABLED_PROGRAMS"][aprogram.name]["start_times"]:
                    dates.append(datetime.datetime.strptime(anitem, '%H:%M').time())
                ENABLED_PROGRAMS.append(aprogram(dates,
                                                 config["ENABLED_PROGRAMS"][aprogram.name]["preparation_needed_mins"]))
            except Exception as e:
                logger.error(f"Could not enable the program: {e.__class__.__name__}")
    logger.info(f"Registered {len(ENABLED_PROGRAMS)} programs.")

def prg_sched_loop():
    register_programs()
    logger.info("Entering program scheduler loop.")
    while True:
        for aprogram in ENABLED_PROGRAMS:
            for atime in aprogram.start_times:
                if is_now_the_minute(atime):
                    if not aprogram.program_running:
                        logger.debug("Starting a program")
                        program_start_thread = Thread(name=f"PrgRunner", target=aprogram.start_program)
                        program_start_thread.start()
                if is_now_the_minute(atime, 0 - aprogram.preparation_needed_mins):
                    if not aprogram.preparations_started:
                        logger.debug("Starting program preparation")
                        program_prep_thread = Thread(name=f"PrgPrep", target=aprogram.prepare_program)
                        program_prep_thread.start()
        sleep(20)

def is_now_the_minute(time_obj, offset_mins = 0):
    dt = datetime.datetime.now()
    return dt.hour == time_obj.hour and dt.minute == (time_obj.minute + offset_mins)