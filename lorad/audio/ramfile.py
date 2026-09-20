import os
import threading

from mutagen.mp3 import MP3

from lorad.common.utils.logger import get_logger
from lorad.common.utils.shm import is_shm_path

logger = get_logger()

BUFFER_BYTES = 16 * 1024 * 1024


def _mb(n: int) -> str:
    return f"{n / (1024 * 1024):.2f} MB"


def format_duration(seconds: float) -> str:
    if not seconds:
        return "unknown length"
    return f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


def format_slot_size(slot: "RamSlot") -> str:
    if slot.file_size > BUFFER_BYTES:
        return f"{_mb(len(slot.data))} in buffer (partial, file {_mb(slot.file_size)})"
    return _mb(slot.file_size)


def file_bitrate_kbps(path: str) -> int:
    try:
        return max(int(round(MP3(path).info.bitrate / 1000)), 0)
    except Exception:
        return 0


def file_duration_s(path: str) -> float:
    try:
        return float(MP3(path).info.length)
    except Exception:
        return 0.0


def read_window(path: str, offset: int, max_bytes: int = BUFFER_BYTES) -> tuple[bytes, int]:
    size = os.path.getsize(path)
    if offset >= size:
        return b"", size
    to_read = min(max_bytes, size - offset)
    with open(path, "rb") as fh:
        fh.seek(offset)
        return fh.read(to_read), size


class RamSlot:
    def __init__(self):
        self.clear()

    def clear(self):
        self.data = b""
        self.name = ""
        self.path = ""
        self.file_offset = 0
        self.file_size = 0
        self.ready = False
        self.kind = None  # "window" | "track"
        self.duration_s = 0.0
        self.bitrate_kbps = 0

    def fill(self, path: str, name: str, offset: int = 0, kind: str = "track"):
        data, size = read_window(path, offset)
        self.data = data
        self.name = name
        self.path = path
        self.file_offset = offset
        self.file_size = size
        self.kind = kind
        self.duration_s = file_duration_s(path) if kind == "track" and offset == 0 else 0.0
        self.bitrate_kbps = file_bitrate_kbps(path)
        self.ready = bool(data)
        if self.ready and is_shm_path(path):
            # Keep the file until the player is done with this track. Unlinking on load
            # made resume after a program hit FileNotFoundError and jump to fallback.
            os.utime(path, None)

    def window_end(self) -> int:
        return self.file_offset + len(self.data)

    def is_last_window(self) -> bool:
        return self.window_end() >= self.file_size


class DoubleBuffer:
    def __init__(self):
        self.current = RamSlot()
        self.preload = RamSlot()
        self.lock = threading.Lock()
        self._loader = None
        self.reserve_preload_for_track = False

    def load_current_track(self, path: str, name: str):
        with self.lock:
            self.reserve_preload_for_track = False
            self.current.fill(path, name, 0, "track")
            self.preload.clear()
        self._maybe_start_window_preload()

    def load_preload_track(self, path: str, name: str):
        with self.lock:
            self.preload.fill(path, name, 0, "track")
            self.reserve_preload_for_track = False

    def release_track_reservation(self):
        """Give the preload slot back to window loading after a track load fell through."""
        with self.lock:
            if not self.reserve_preload_for_track:
                return
            self.reserve_preload_for_track = False
        self._maybe_start_window_preload()

    def swap(self):
        with self.lock:
            self.current, self.preload = self.preload, self.current
            self.preload.clear()
            promoted = self.current
        if promoted.kind == "window":
            logger.info(
                f"Buffer bank switch: {promoted.name} "
                f"window {_mb(promoted.file_offset)}–{_mb(promoted.window_end())} "
                f"of {_mb(promoted.file_size)}"
            )
        self._maybe_start_window_preload()

    def _maybe_start_window_preload(self):
        with self.lock:
            cur = self.current
            if not cur.ready or cur.is_last_window():
                return
            if self.reserve_preload_for_track:
                return
            if self.preload.ready:
                return
            path, name, nxt = cur.path, cur.name, cur.window_end()
        self._start_loader(lambda: self._fill_window(path, name, nxt))

    def _fill_window(self, path, name, offset):
        with self.lock:
            if self.reserve_preload_for_track:
                return
            if self.preload.ready and self.preload.kind == "track":
                return
            self.preload.fill(path, name, offset, "window")
        logger.debug(f"Preloaded window {offset} of {path} ({len(self.preload.data)} bytes)")

    def _start_loader(self, fn):
        if self._loader is not None and self._loader.is_alive():
            return
        self._loader = threading.Thread(name="RamFill", target=fn, daemon=True)
        self._loader.start()

    def wait_preload(self, timeout=120) -> bool:
        waited = 0.0
        while waited < timeout:
            with self.lock:
                if self.preload.ready:
                    return True
            threading.Event().wait(0.1)
            waited += 0.1
        return False
