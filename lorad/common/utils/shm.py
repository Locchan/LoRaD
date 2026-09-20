import json
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

# Voiced news is kept so the same headlines are not sent to the TTS again. It is only
# given up when shm gets tight, and then just a few files at a time.
NEUROVOICE_DIRNAME = "neurovoice"
NEUROVOICE_TRIM_AT_USAGE = 0.5
NEUROVOICE_TRIM_COUNT = 4
_pause_lock = threading.Lock()
_paused_until = None
_pause_reason = ""


def pause_cleanup(reason: str, hold_s: float):
    """Hold the janitor off until hold_s has elapsed (or resume_cleanup is called)."""
    global _paused_until, _pause_reason
    until = time.monotonic() + max(0.0, float(hold_s))
    with _pause_lock:
        _paused_until = until
        _pause_reason = reason
    logger.debug(f"shm cleanup paused for {hold_s:.0f}s: {reason}")


def resume_cleanup():
    global _paused_until, _pause_reason
    with _pause_lock:
        if _paused_until is None:
            return
        _paused_until = None
        _pause_reason = ""
    logger.debug("shm cleanup resumed")


def cleanup_paused() -> bool:
    global _paused_until, _pause_reason
    with _pause_lock:
        if _paused_until is None:
            return False
        if time.monotonic() < _paused_until:
            return True
        logger.info(f"shm cleanup pause for [{_pause_reason}] expired, resuming")
        _paused_until = None
        _pause_reason = ""
    return False


def shm_usage() -> float:
    """Fraction of the shm filesystem in use, 0.0 if it cannot be read."""
    try:
        stat = os.statvfs(SHM_ROOT)
    except OSError:
        return 0.0
    total = stat.f_blocks
    if not total:
        return 0.0
    return (total - stat.f_bfree) / total

# Fixed homes for the on-disk assets we copy in at boot. The config keeps pointing at the
# real directories; code reads the copies from here.
PINNED_RES = os.path.join(SHM_PINNED, "res")
PINNED_DATA = os.path.join(SHM_PINNED, "data")
PINNED_FALLBACK = os.path.join(SHM_PINNED, "fallback")
PINNED_YANDEX_STATIONS = os.path.join(SHM_PINNED, "yandex_available_stations.json")


def write_pinned_json(path: str, payload) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, mode=0o700, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    os.replace(tmp, path)


def read_pinned_json(path: str):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Could not read pinned json {path}: {e}")
        return None


def write_yandex_stations(stations: dict) -> None:
    write_pinned_json(PINNED_YANDEX_STATIONS, stations)


def read_yandex_stations() -> dict | None:
    payload = read_pinned_json(PINNED_YANDEX_STATIONS)
    if isinstance(payload, dict):
        return payload
    return None


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
    logger.debug(f"Pinned media in shm: {src} -> {dest}")
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
        if _pin_file(src, dest):
            logger.info(f"Pinned 1 file into shm: {src} -> {dest}")
        else:
            logger.info(f"Pinned media already in shm: {src} -> {dest}")
        return dest
    copied = 0
    seen = 0
    for root, dirs, files in os.walk(src):
        dirs[:] = [name for name in dirs if name not in PINNED_IGNORE]
        rel = os.path.relpath(root, src)
        for name in files:
            if name in PINNED_IGNORE:
                continue
            src_file = os.path.join(root, name)
            dest_file = os.path.join(dest, name) if rel == "." else os.path.join(dest, rel, name)
            seen += 1
            if _pin_file(src_file, dest_file):
                copied += 1
    already = seen - copied
    if copied:
        extra = f", {already} already present" if already else ""
        logger.info(f"Pinned {copied} files into shm{extra}: {src} -> {dest}")
    else:
        logger.info(f"Pinned media already in shm ({seen} files): {src} -> {dest}")
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


def trim_neurovoice():
    """Drop the few oldest voiced files, but only once shm is filling up."""
    usage = shm_usage()
    if usage < NEUROVOICE_TRIM_AT_USAGE:
        return 0
    newsdir = os.path.join(SHM_ROOT, NEUROVOICE_DIRNAME)
    candidates = []
    for root, _, files in os.walk(newsdir):
        for filename in files:
            path = os.path.join(root, filename)
            try:
                candidates.append((os.path.getmtime(path), path))
            except OSError:
                pass
    if not candidates:
        return 0
    candidates.sort()
    removed = 0
    for _, path in candidates[:NEUROVOICE_TRIM_COUNT]:
        if unlink_shm(path):
            removed += 1
    if removed:
        logger.info(f"shm at {usage:.0%}, dropped {removed} oldest news voice files")
    return removed


def cleanup_orphans(max_age_s: int = ORPHAN_MAX_AGE_S):
    cutoff = time.time() - max_age_s
    pinned_name = os.path.basename(SHM_PINNED)
    for root, dirs, files in os.walk(SHM_ROOT, topdown=True):
        if pinned_name in dirs:
            dirs.remove(pinned_name)
        if NEUROVOICE_DIRNAME in dirs:
            # Voiced news is not aged out; trim_neurovoice decides when it goes.
            dirs.remove(NEUROVOICE_DIRNAME)
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
            # An empty dir is usually one something just made to write into (news digests),
            # so only reap it once it has been sitting unused for as long as the files.
            if os.path.getmtime(root) < cutoff:
                os.rmdir(root)
        except OSError:
            pass


def start_shm_janitor():
    def run():
        while True:
            time.sleep(60)
            if cleanup_paused():
                continue
            cleanup_orphans()
            trim_neurovoice()

    threading.Thread(name="ShmJanitor", target=run, daemon=True).start()
