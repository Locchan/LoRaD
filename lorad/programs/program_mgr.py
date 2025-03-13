import datetime
from threading import Thread
from time import sleep
from lorad.programs.GenericPrg import GenericPrg
from lorad.programs.NewsPrgS import NewsPrgS
from lorad.utils.logger import get_logger
from lorad.utils.utils import read_config
from lorad.server.LoRadSrv import LoRadServer


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
                    if not aprogram.program_running and LoRadServer.connected_clients > 0:
                            logger.debug("Starting a program")
                            program_start_thread = Thread(name="PrgRunner", target=aprogram.start_program)
                            program_start_thread.start()
                if is_now_the_minute(atime, 0 - aprogram.preparation_needed_mins):
                    if not aprogram.preparations_started and LoRadServer.connected_clients > 0:
                        logger.debug("Starting program preparation")
                        program_prep_thread = Thread(name="PrgPrep", target=aprogram.prepare_program)
                        program_prep_thread.start()
        sleep(20)


def is_now_the_minute(time_obj: datetime.time, offset_mins: int = 0):
    now = datetime.datetime.now()
    dt_tmp = datetime.datetime.combine(datetime.datetime.today(), time_obj)
    dt_tmp += datetime.timedelta(minutes=offset_mins)
    time_to_check = dt_tmp.time()

    return f"{now.time().hour}:{now.time().minute}" == f"{time_to_check.hour}:{time_to_check.minute}"
