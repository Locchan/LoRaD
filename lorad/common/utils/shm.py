import os
import shutil
import threading
import time

from lorad.common.utils.logger import get_logger

logger = get_logger()

SHM_ROOT = "/dev/shm/lorad"
SHM_PINNED = os.path.join(SHM_ROOT, "pinned")
ORPHAN_MAX_AGE_S = 60 * 60
PINNED_IGNORE = ("neurovoice",)

# Fixed homes for the on-disk assets we copy in at boot. The config keeps pointing at the
# real directories; code reads the copies from here.
PINNED_RES = os.path.join(SHM_PINNED, "res")
PINNED_DATA = os.path.join(SHM_PINNED, "data")
PINNED_FALLBACK = os.path.join(SHM_PINNED, "fallback")


def pinned_path(root: str, *parts: str) -> str:
    # Config values may carry Windows separators; they are relative to a pinned root here.
    cleaned = [str(part).replace("\\", os.sep).strip(os.sep) for part in parts if part]
    return os.path.join(root, *cleaned)


def prepare_shm() -> str:
    if not os.path.isdir("/dev/shm"):
        raise RuntimeError("/dev/shm is unavailable; LoRaD requires shared memory")
    os.makedirs(SHM_ROOT, mode=0o700, exist_ok=True)
    os.makedirs(SHM_PINNED, mode=0o700, exist_ok=True)
    for name in os.listdir(SHM_ROOT):
        if name == os.path.basename(SHM_PINNED):
            continue
        path = os.path.join(SHM_ROOT, name)
        try:
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        except OSError as e:
            logger.warning(f"Could not clear {path}: {e}")
    logger.info(f"Transient media workspace: {SHM_ROOT}")
    return SHM_ROOT


def cleanup_shm():
    if not os.path.isdir(SHM_ROOT):
        return
    for name in os.listdir(SHM_ROOT):
        if name == os.path.basename(SHM_PINNED):
            continue
        path = os.path.join(SHM_ROOT, name)
        try:
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        except OSError:
            pass


def shm_path(*parts: str) -> str:
    path = os.path.join(SHM_ROOT, *parts)
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    return path


def is_shm_path(path: str) -> bool:
    try:
        return os.path.commonpath((os.path.realpath(path), SHM_ROOT)) == SHM_ROOT
    except (TypeError, ValueError):
        return False


def is_pinned_shm(path: str) -> bool:
    try:
        return os.path.commonpath((os.path.realpath(path), SHM_PINNED)) == SHM_PINNED
    except (TypeError, ValueError, OSError):
        return False


def unlink_shm(path: str) -> bool:
    if not is_shm_path(path):
        return False
    if is_pinned_shm(path):
        logger.debug(f"Leaving pinned media: {path}")
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


def _file_size(path: str) -> int | None:
    try:
        return os.stat(path).st_size
    except OSError:
        return None


def _pin_file(src: str, dest: str) -> bool:
    # Same rule as gimn.sh: copy only if the pinned file is missing or a different size.
    src_size = _file_size(src)
    if src_size is None:
        return False
    if os.path.isfile(dest) and _file_size(dest) == src_size:
        return False
    parent = os.path.dirname(dest)
    if parent:
        os.makedirs(parent, mode=0o700, exist_ok=True)
    shutil.copy2(src, dest)
    logger.info(f"Pinned media in shm: {src} -> {dest}")
    return True


def _pin_tree(src: str, dest: str) -> str | None:
    if src and is_pinned_shm(src):
        logger.error(f"Config points at pinned shm instead of on-disk media: {src}")
        return None
    if not src or not os.path.exists(src):
        logger.warning(f"Nothing to pin into shm: {src}")
        return None
    os.makedirs(SHM_PINNED, mode=0o700, exist_ok=True)
    if os.path.isfile(src):
        _pin_file(src, dest)
        return dest
    copied = 0
    for root, dirs, files in os.walk(src):
        dirs[:] = [name for name in dirs if name not in PINNED_IGNORE]
        rel = os.path.relpath(root, src)
        for name in files:
            if name in PINNED_IGNORE:
                continue
            src_file = os.path.join(root, name)
            dest_file = os.path.join(dest, name) if rel == "." else os.path.join(dest, rel, name)
            if _pin_file(src_file, dest_file):
                copied += 1
    if copied == 0:
        logger.info(f"Pinned media already in shm: {src} -> {dest}")
    return dest


def seed_pinned_assets(config: dict) -> None:
    """Copy the configured on-disk assets into shm. The config keeps the on-disk paths."""
    from lorad.common.utils.misc import local_path

    for key, dest in (
        ("RESDIR", PINNED_RES),
        ("DATADIR", PINNED_DATA),
        ("FALLBACK_TRACK_DIR", PINNED_FALLBACK),
    ):
        src = local_path(config.get(key, ""))
        if src:
            _pin_tree(src, dest)


def cleanup_orphans(max_age_s: int = ORPHAN_MAX_AGE_S):
    cutoff = time.time() - max_age_s
    pinned_name = os.path.basename(SHM_PINNED)
    for root, dirs, files in os.walk(SHM_ROOT, topdown=True):
        if pinned_name in dirs:
            dirs.remove(pinned_name)
        if is_pinned_shm(root):
            dirs[:] = []
            continue
        for filename in files:
            path = os.path.join(root, filename)
            try:
                if os.path.getmtime(path) < cutoff:
                    unlink_shm(path)
            except FileNotFoundError:
                pass
        if root == SHM_ROOT:
            continue
        try:
            os.rmdir(root)
        except OSError:
            pass


def start_shm_janitor():
    def run():
        while True:
            time.sleep(60)
            cleanup_orphans()

    threading.Thread(name="ShmJanitor", target=run, daemon=True).start()
