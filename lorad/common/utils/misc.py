import datetime
import json
import os
import shutil
import signal

CONFIG = {}
CONFIG_PATH = None

def resolve_jsonc_path(filepath):
    if os.path.exists(filepath):
        return filepath
    root, ext = os.path.splitext(filepath)
    ext_l = ext.lower()
    if ext_l == ".json":
        alt = root + ".jsonc"
    elif ext_l == ".jsonc":
        alt = root + ".json"
    else:
        return None
    if os.path.exists(alt):
        return alt
    return None

def _missing_jsonc_hint(filepath):
    root, ext = os.path.splitext(filepath)
    ext_l = ext.lower()
    if ext_l == ".json":
        return f"'{filepath}' or '{root}.jsonc'"
    if ext_l == ".jsonc":
        return f"'{filepath}' or '{root}.json'"
    return f"'{filepath}'"

def _strip_jsonc_comments(text):
    out = []
    i = 0
    n = len(text)
    in_str = False
    esc = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "/":
                i += 2
                while i < n and text[i] not in "\n\r":
                    i += 1
                continue
            if nxt == "*":
                i += 2
                while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                    i += 1
                i = min(n, i + 2)
                continue
        out.append(c)
        i += 1
    return "".join(out)

def _strip_trailing_commas(text):
    out = []
    i = 0
    n = len(text)
    in_str = False
    esc = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == ",":
            j = i + 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            if j < n and text[j] in "]}":
                i += 1
                continue
        out.append(c)
        i += 1
    return "".join(out)

def loads_jsonc(text):
    # JSONC: // and /* */ comments, trailing commas. Strings are left intact.
    text = text.lstrip("\ufeff")
    return json.loads(_strip_trailing_commas(_strip_jsonc_comments(text)))

def load_jsonc_file(filepath):
    with open(filepath, "r", encoding="utf-8") as fh:
        return loads_jsonc(fh.read())

# This will read config only once on startup and then return this every time it is called.
#  Passing reload as True will force the function to actually re-read the config from disk.
def read_config(filepath="config.json", reload=False):
    global CONFIG, CONFIG_PATH

    if "CFGFILE_PATH" in os.environ:
        filepath = os.environ["CFGFILE_PATH"]

    resolved = resolve_jsonc_path(filepath)
    if resolved is None:
        print("Config file not found. The file should reside in path provided by CFGFILE_PATH environment variable or in './config.json' / './config.jsonc'.")
        print(f"Expected to find the config file at {_missing_jsonc_hint(filepath)}")
        exit(1)
    filepath = resolved
    if CONFIG == {} and not reload:
        try:
            CONFIG = load_jsonc_file(filepath)
            CONFIG_PATH = filepath
            if "DEBUG" in CONFIG and CONFIG["DEBUG"]:
                print(f"Read config:\n{json.dumps(CONFIG, indent=2)}")
            return CONFIG
        except Exception as e:
            print(f"Could not read config file {filepath}: {e.__class__.__name__}")
            exit(1)
    else:
        return CONFIG

def write_config(data, filepath="config.json"):
    global CONFIG_PATH
    if CONFIG_PATH:
        filepath = CONFIG_PATH
    elif "CFGFILE_PATH" in os.environ:
        filepath = os.environ["CFGFILE_PATH"]
        filepath = resolve_jsonc_path(filepath) or filepath
    else:
        filepath = resolve_jsonc_path(filepath) or filepath
    #shutil.copyfile(filepath, filepath + f"{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}" + ".bak")
    # Comments in the on-disk file are not preserved.
    with open(filepath, "w", encoding="utf-8") as config_file:
        json.dump(data, config_file, indent=2)
    read_config(filepath, reload=True)

def local_path(*parts):
    # On-disk assets (resources, fallback tracks) live outside shm. Config may carry
    # Windows separators, and ffmpeg resolves relative paths against its own cwd/list file,
    # so always hand it an absolute native path.
    cleaned = [str(apart).replace("\\", os.sep) for apart in parts if apart]
    if not cleaned:
        return ""
    return os.path.abspath(os.path.join(*cleaned))

def feature_enabled(feature_name):
    config = read_config()
    return feature_name in config["ENABLED_FEATURES"]
    
def read_stations(filepath="stations.json"):
    config = read_config()

    if "STATIONS_FILE_PATH" in config:
        filepath = config["STATIONS_FILE_PATH"]

    resolved = resolve_jsonc_path(filepath)
    if resolved is None:
        print("Stations config file not found. The file should reside in path provided by STATIONS_FILE_PATH main configuration file entry or in './stations.json' / './stations.jsonc'.")
        print(f"Expected to find the stations config file at {_missing_jsonc_hint(filepath)}")
        exit(1)
    filepath = resolved

    try:
        return load_jsonc_file(filepath)
    except Exception as e:
        print(f"Could not read config file {filepath}: {e.__class__.__name__}")
        exit(1)

def signal_stop(_signo, _stack_frame):
    from lorad.common.utils.logger import get_logger
    from lorad.common.utils.shm import cleanup_shm
    logger = get_logger()
    logger.info(f"Caught {signal.Signals(_signo).name}. Shutting down...")
    cleanup_shm()
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

