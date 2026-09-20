import os
import shutil
import threading
import time

from lorad.common.utils.logger import get_logger

logger = get_logger()

SHM_ROOT = "/dev/shm/lorad"
ORPHAN_MAX_AGE_S = 60 * 60


def prepare_shm() -> str:
    if not os.path.isdir("/dev/shm"):
        raise RuntimeError("/dev/shm is unavailable; LoRaD requires shared memory")
    shutil.rmtree(SHM_ROOT, ignore_errors=True)
    os.makedirs(SHM_ROOT, mode=0o700, exist_ok=True)
    logger.info(f"Transient media workspace: {SHM_ROOT}")
    return SHM_ROOT


def cleanup_shm():
    shutil.rmtree(SHM_ROOT, ignore_errors=True)


def shm_path(*parts: str) -> str:
    path = os.path.join(SHM_ROOT, *parts)
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    return path


def is_shm_path(path: str) -> bool:
    try:
        return os.path.commonpath((os.path.realpath(path), SHM_ROOT)) == SHM_ROOT
    except (TypeError, ValueError):
        return False


def unlink_shm(path: str) -> bool:
    if not is_shm_path(path):
        return False
    try:
        os.remove(path)
        logger.debug(f"Deleted transient media: {path}")
        return True
    except FileNotFoundError:
        return False
    except OSError as e:
        logger.warning(f"Could not delete transient media {path}: {e}")
        return False


def cleanup_orphans(max_age_s: int = ORPHAN_MAX_AGE_S):
    cutoff = time.time() - max_age_s
    for root, dirs, files in os.walk(SHM_ROOT, topdown=False):
        for filename in files:
            path = os.path.join(root, filename)
            try:
                if os.path.getmtime(path) < cutoff:
                    unlink_shm(path)
            except FileNotFoundError:
                pass
        for dirname in dirs:
            try:
                os.rmdir(os.path.join(root, dirname))
            except OSError:
                pass


def start_shm_janitor():
    def run():
        while True:
            time.sleep(60)
            cleanup_orphans()

    threading.Thread(name="ShmJanitor", target=run, daemon=True).start()
