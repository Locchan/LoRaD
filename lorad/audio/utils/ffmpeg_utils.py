import os
import subprocess
import tempfile
from lorad.common.utils.logger import get_logger
from lorad.common.utils.misc import read_config
from lorad.common.utils.shm import SHM_ROOT, is_shm_path, unlink_shm


logger = get_logger()
config = read_config()

MAX_LOGGED_FFMPEG_LINES = 20


def _debug_enabled() -> bool:
    return bool(config.get("DEBUG"))


def _loglevel_args() -> list[str]:
    # Never "quiet": a failure with no reason in the log is impossible to act on.
    return ["-loglevel", "info" if _debug_enabled() else "error"]


def _run_ffmpeg(command: list[str], what: str) -> bool:
    logger.debug(f"{what} command: {' '.join(command)}")
    result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    output = (result.stderr or "").strip()
    if result.returncode == 0:
        if output:
            logger.debug(f"ffmpeg: {output}")
        return True
    logger.error(f"{what} finished with errors (rc={result.returncode}).")
    for line in output.splitlines()[-MAX_LOGGED_FFMPEG_LINES:]:
        logger.error(f"ffmpeg: {line}")
    return False


def ffmpeg_reencode(filename: str, params: list[str], output_filename: str):
    if not is_shm_path(output_filename):
        raise RuntimeError(f"Refusing to encode outside shared memory: {output_filename}")
    ffmpeg_command = ["ffmpeg", *_loglevel_args(), "-i", filename]
    ffmpeg_command.extend(params)
    ffmpeg_command.append(output_filename)
    if not _run_ffmpeg(ffmpeg_command, "Re-encoder"):
        unlink_shm(output_filename)


def ffmpeg_concatenate(filenames: list[str], output_filename: str, artist=None, title=None):
    if not is_shm_path(output_filename):
        raise RuntimeError(f"Refusing to concatenate outside shared memory: {output_filename}")
    ffmpeg_command = ["ffmpeg", *_loglevel_args(), "-f", "concat", "-safe", "0", "-i"]
    entries = [os.path.abspath(filename) for filename in filenames]
    list_filename = ""
    with tempfile.NamedTemporaryFile(
        "w", dir=config.get("RUNTIME_MEDIA_DIR", SHM_ROOT), delete=False, suffix=".txt"
    ) as f:
        for entry in entries:
            # The list lives in shm, and ffmpeg resolves relative entries against it.
            f.write("file '{}'\n".format(entry.replace("'", r"'\''")))
        list_filename = f.name
    try:
        ffmpeg_command.extend([list_filename, "-c", "copy"])
        if artist is not None:
            ffmpeg_command.extend(["-metadata", f"artist='{artist}'"])
        if title is not None:
            ffmpeg_command.extend(["-metadata", f"title='{title}'"])
        ffmpeg_command.append(output_filename)
        if not _run_ffmpeg(ffmpeg_command, "Concatenator"):
            # Usually one of the inputs went missing, so name them all.
            for entry in entries:
                logger.error(f"Concat input: {entry} (exists: {os.path.exists(entry)})")
            unlink_shm(output_filename)
    finally:
        unlink_shm(list_filename)
