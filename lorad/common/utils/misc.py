import json
import os
import signal

def read_config(filepath="config.json"):
    if "CFGFILE_PATH" in os.environ:
        filepath = os.environ["CFGFILE_PATH"]

    if not os.path.exists(filepath):
        print("Config file not found. The file should reside in path provided by CFGFILE_PATH environment variable or in './config.json'.")
        print(f"Expected to find the config file at '{filepath}'")
        exit(1)

    with open(filepath, "r", encoding="utf-8") as config_file:
        try:
            return json.load(config_file)
        except Exception as e:
            print(f"Could not read config file {filepath}: {e.__class__.__name__}")
            exit(1)

def feature_enabled(feature_name):
    config = read_config()
    return feature_name in config["ENABLED_FEATURES"]
    
def read_stations(filepath="stations.json"):
    config = read_config()

    if not os.path.exists(filepath):
        print("Stations config file not found. The file should reside in path provided by STATIONS_FILE_PATH environment variable or in './stations.json'.")
        print(f"Expected to find the stations config file at '{filepath}'")
        exit(1)

    if "STATIONS_FILE_PATH" in config:
        filepath = config["STATIONS_FILE_PATH"]
    with open(filepath, "r", encoding="utf-8") as config_file:
        try:
            return json.load(config_file)
        except Exception as e:
            print(f"Could not read config file {filepath}: {e.__class__.__name__}")
            exit(1)

def signal_stop(_signo, _stack_frame):
    from lorad.common.utils.logger import get_logger
    logger = get_logger()
    logger.info(f"Caught {signal.Signals(_signo).name}. Shutting down...")
    os._exit(0)

def splash():
    from lorad.common.utils.logger import get_logger
    logger = get_logger()
    splash_text = """
  _           _____       _____  
 | |         |  __ \\     |  __ \\ 
 | |     ___ | |__) |__ _| |  | |
 | |    / _ \\|  _  // _` | |  | |
 | |___| (_) | | \\ \\ (_| | |__| |
 |______\\___/|_|  \\_\\__,_|_____/ 
"""
    lines = splash_text.split("\n")
    for aline in lines:
        logger.info(aline)
    logger.info(get_version())
    logger.info("")

def get_version(path="/version"):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as versionfile:
            return versionfile.readline().strip()
    else:
        return "Unknown version"

