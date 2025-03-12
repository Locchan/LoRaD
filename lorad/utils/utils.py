import json
import os
import signal

from lorad.utils.logger import get_logger

def read_config(filepath="config.json"):
    if "CFGFILE_PATH" in os.environ:
        filepath = os.environ["CFGFILE_PATH"]
    with open(filepath, "r") as config_file:
        try:
            return json.load(config_file)
        except Exception as e:
            print(f"Could not read config file {filepath}: {e.__class__.__name__}")
            exit(1)

def signal_stop(_signo, _stack_frame):
    logger = get_logger()
    logger.info(f"Caught {signal.Signals(_signo).name}. Shutting down...")
    os._exit(0)

def splash():
    logger = get_logger()
    splash = f"""
  _           _____       _____  
 | |         |  __ \\     |  __ \\ 
 | |     ___ | |__) |__ _| |  | |
 | |    / _ \\|  _  // _` | |  | |
 | |___| (_) | | \\ \\ (_| | |__| |
 |______\\___/|_|  \\_\\__,_|_____/ 
"""
    lines = splash.split("\n")
    for aline in lines:
        logger.info(aline)
    if "VERSION" in os.environ:
        logger.info(os.environ["VERSION"])