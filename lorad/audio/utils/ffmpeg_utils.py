import subprocess
import os
import tempfile
from lorad.common.utils.logger import get_logger
from lorad.common.utils.misc import read_config


logger = get_logger()
config = read_config()

def ffmpeg_reencode(filename: str, params: list[str], output_filename: str):
    ffmpeg_command = ["ffmpeg", "-i", filename]
    ffmpeg_command.extend(params)
    if not ("DEBUG" in config and config["DEBUG"]):
        ffmpeg_command.extend(["-loglevel", "quiet"])
    ffmpeg_command.append(output_filename)
    logger.debug(f"Re-encoder command: {' '.join(ffmpeg_command)}")
    rc = subprocess.call(ffmpeg_command)
    if rc != 0:
        logger.error("Reencoding finished with errors.")
    

def ffmpeg_concatenate(filenames: list[str], output_filename: str, artist=None, title=None):
    if "DEBUG" in config and config["DEBUG"]:
        ffmpeg_command = ["ffmpeg", "-f", "concat", "-safe", "0", "-i"]
    else:
        ffmpeg_command = ["ffmpeg", "-loglevel", "quiet", "-f", "concat", "-safe", "0", "-i"]
    list_filename = ""
    with tempfile.NamedTemporaryFile("w", dir=".", delete=False, suffix=".txt") as f:
        for filename in filenames:
            f.write(f"file '{filename}'\n")
        list_filename = f.name
    ffmpeg_command.extend([list_filename, "-c", "copy"])
    if artist is not None:
        ffmpeg_command.extend(["-metadata", f"artist='{artist}'"])
    if title is not None:
        ffmpeg_command.extend(["-metadata", f"title='{title}'"])
    ffmpeg_command.append(output_filename)
    logger.debug(f"Concatenator command: {' '.join(ffmpeg_command)}")
    rc = subprocess.call(ffmpeg_command)
    if rc != 0:
        logger.error("Concatenation finished with errors.")
    os.remove(list_filename)
