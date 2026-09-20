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


def _pin_tree(src: str, dest_name: str) -> str | None:
    if not src or not os.path.exists(src):
        logger.warning(f"Nothing to pin into shm: {src}")
        return None
    dest = os.path.join(SHM_PINNED, dest_name)
    os.makedirs(SHM_PINNED, mode=0o700, exist_ok=True)
    if os.path.isdir(src):
        shutil.copytree(
            src,
            dest,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(*PINNED_IGNORE),
        )
    else:
        parent = os.path.dirname(dest)
        if parent:
            os.makedirs(parent, mode=0o700, exist_ok=True)
        shutil.copy2(src, dest)
    logger.info(f"Pinned media in shm: {src} -> {dest}")
    return dest


def _under(child: str, parent: str) -> bool:
    try:
        return os.path.commonpath(
            (os.path.realpath(child), os.path.realpath(parent))
        ) == os.path.realpath(parent)
    except (TypeError, ValueError, OSError):
        return False


def seed_pinned_assets(config: dict) -> None:
    from lorad.common.utils.misc import local_path

    res_src = local_path(config.get("RESDIR", ""))
    data_src = local_path(config.get("DATADIR", ""))
    fallback_src = local_path(config.get("FALLBACK_TRACK_DIR", ""))

    res_dest = _pin_tree(res_src, "res") if res_src else None
    if res_dest:
        config["RESDIR"] = res_dest

    if data_src and res_src and os.path.realpath(data_src) == os.path.realpath(res_src) and res_dest:
        config["DATADIR"] = res_dest
    elif data_src and res_src and _under(data_src, res_src) and res_dest:
        config["DATADIR"] = os.path.join(res_dest, os.path.relpath(data_src, res_src))
    elif data_src:
        data_dest = _pin_tree(data_src, "data")
        if data_dest:
            config["DATADIR"] = data_dest

    if fallback_src and res_src and _under(fallback_src, res_src) and res_dest:
        config["FALLBACK_TRACK_DIR"] = os.path.join(res_dest, os.path.relpath(fallback_src, res_src))
    elif fallback_src:
        fallback_dest = _pin_tree(fallback_src, "fallback")
        if fallback_dest:
            config["FALLBACK_TRACK_DIR"] = fallback_dest


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
