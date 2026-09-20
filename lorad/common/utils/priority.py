"""Scheduling for the audio path.

A hiccup is a missed deadline, so the threads that pace and ship audio run on
SCHED_FIFO and the process (ffmpeg children included, they inherit it) runs at a
negative nice. Everything is best effort: without CAP_SYS_NICE this is a no-op.
"""

import ctypes
import os
import platform
import threading

from lorad.common.utils.logger import get_logger

logger = get_logger()

SCHED_FIFO = 1
# Low enough to stay under anything the kernel runs, high enough to beat normal work.
AUDIO_PRIORITY = 10
PROCESS_NICE = -11

# musl answers sched_setscheduler with ENOSYS, so on Alpine the syscall is issued directly.
_SETSCHEDULER_SYSCALL = {"aarch64": 119, "armv7l": 156, "armv6l": 156, "x86_64": 144, "i686": 156}

_warned = False


class _SchedParam(ctypes.Structure):
    _fields_ = [("sched_priority", ctypes.c_int)]


def boost_process(nice_value: int = PROCESS_NICE) -> bool:
    try:
        os.nice(nice_value - os.nice(0))
    except OSError as e:
        logger.warning(f"Could not renice to {nice_value}: {e}")
        return False
    logger.info(f"Process niceness: {os.nice(0)}")
    return True


def _raw_setscheduler(tid: int, priority: int) -> bool:
    number = _SETSCHEDULER_SYSCALL.get(platform.machine())
    if number is None:
        return False
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        libc.syscall.restype = ctypes.c_long
        return libc.syscall(number, tid, SCHED_FIFO, ctypes.byref(_SchedParam(priority))) == 0
    except OSError:
        return False


def realtime_thread(priority: int = AUDIO_PRIORITY) -> bool:
    """Move the calling thread to SCHED_FIFO."""
    global _warned
    tid = threading.get_native_id()
    name = threading.current_thread().name
    try:
        os.sched_setscheduler(tid, os.SCHED_FIFO, os.sched_param(priority))
        logger.debug(f"Thread {name} is realtime (prio {priority})")
        return True
    except (AttributeError, OSError):
        pass
    if _raw_setscheduler(tid, priority):
        logger.debug(f"Thread {name} is realtime (prio {priority})")
        return True
    if not _warned:
        _warned = True
        logger.warning("Could not switch audio threads to realtime scheduling")
    return False
