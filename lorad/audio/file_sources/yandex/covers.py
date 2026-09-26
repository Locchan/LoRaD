"""Async Yandex cover art into cleanable SHM (/dev/shm/lorad/covers)."""
import os
import threading

from lorad.common.utils.logger import get_logger
from lorad.common.utils.shm import shm_path, unlink_shm

logger = get_logger()

COVER_SIZE = "200x200"
_lock = threading.Lock()
_inflight: set[str] = set()


def cover_shm_path(track_id: str) -> str:
    safe = str(track_id).replace("/", "_").replace(":", "_")
    return shm_path("covers", f"yandex_{safe}.jpg")


def touch_cover(path: str) -> None:
    try:
        os.utime(path, None)
    except OSError:
        pass


def cover_ready(track_id: str) -> bool:
    path = cover_shm_path(track_id)
    if not os.path.isfile(path):
        return False
    touch_cover(path)
    return True


def read_cover_bytes(track_id: str) -> bytes | None:
    path = cover_shm_path(track_id)
    if not os.path.isfile(path):
        return None
    touch_cover(path)
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError as e:
        logger.warning(f"Could not read cover {path}: {e}")
        return None


def ensure_cover_async(track) -> None:
    """Kick a CoverFetch thread if this track's JPEG is not already in shm."""
    if track is None:
        return
    track_id = getattr(track, "track_id", None) or getattr(track, "id", None)
    if track_id is None:
        return
    track_id = str(track_id)
    path = cover_shm_path(track_id)
    if os.path.isfile(path):
        touch_cover(path)
        return
    with _lock:
        if track_id in _inflight:
            return
        _inflight.add(track_id)
    threading.Thread(
        name="CoverFetch",
        target=_download_cover,
        args=(track, track_id, path),
        daemon=True,
    ).start()


def _download_cover(track, track_id: str, path: str) -> None:
    partial = path + ".part"
    try:
        if os.path.isfile(path):
            touch_cover(path)
            return
        unlink_shm(partial)
        track.download_cover(filename=partial, size=COVER_SIZE)
        os.replace(partial, path)
        logger.debug(f"Cached Yandex cover for {track_id}")
    except Exception as e:
        logger.warning(f"Yandex cover download failed for {track_id}: {e.__class__.__name__}: {e}")
        unlink_shm(partial)
    finally:
        with _lock:
            _inflight.discard(track_id)
