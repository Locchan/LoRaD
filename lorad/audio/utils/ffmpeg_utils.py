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
        ffmpeg_command.extend(["loglevel", "quiet"])
    ffmpeg_command.append(output_filename)
    logger.debug(f"Re-encoder command: {' '.join(ffmpeg_command)}")
    subprocess.call(ffmpeg_command)
    

def ffmpeg_concatenate(filenames: list[str], output_filename: str, artist=None, title=None):
    ffmpeg_command = ["ffmpeg", "-f", "concat", "-safe", "0", "-i"]
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
    logger.debug(f"Re-encoder command: {' '.join(ffmpeg_command)}")
    subprocess.call(ffmpeg_command)
    os.remove(list_filename)
