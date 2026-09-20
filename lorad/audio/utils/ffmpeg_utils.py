import os
import subprocess
import tempfile
from lorad.common.utils.logger import get_logger
from lorad.common.utils.misc import read_config
from lorad.common.utils.shm import SHM_ROOT, is_shm_path, unlink_shm


logger = get_logger()
config = read_config()

def ffmpeg_reencode(filename: str, params: list[str], output_filename: str):
    if not is_shm_path(output_filename):
        raise RuntimeError(f"Refusing to encode outside shared memory: {output_filename}")
    ffmpeg_command = ["ffmpeg", "-i", filename]
    ffmpeg_command.extend(params)
    if not ("DEBUG" in config and config["DEBUG"]):
        ffmpeg_command.extend(["-loglevel", "quiet"])
    ffmpeg_command.append(output_filename)
    logger.debug(f"Re-encoder command: {' '.join(ffmpeg_command)}")
    rc = subprocess.call(ffmpeg_command)
    if rc != 0:
        logger.error("Reencoding finished with errors.")
        unlink_shm(output_filename)
    

def ffmpeg_concatenate(filenames: list[str], output_filename: str, artist=None, title=None):
    if not is_shm_path(output_filename):
        raise RuntimeError(f"Refusing to concatenate outside shared memory: {output_filename}")
    if "DEBUG" in config and config["DEBUG"]:
        ffmpeg_command = ["ffmpeg", "-f", "concat", "-safe", "0", "-i"]
    else:
        ffmpeg_command = ["ffmpeg", "-loglevel", "quiet", "-f", "concat", "-safe", "0", "-i"]
    list_filename = ""
    with tempfile.NamedTemporaryFile(
        "w", dir=config.get("RUNTIME_MEDIA_DIR", SHM_ROOT), delete=False, suffix=".txt"
    ) as f:
        for filename in filenames:
            # The list lives in shm, and ffmpeg resolves relative entries against it.
            f.write("file '{}'\n".format(os.path.abspath(filename).replace("'", r"'\''")))
        list_filename = f.name
    try:
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
            unlink_shm(output_filename)
    finally:
        unlink_shm(list_filename)
