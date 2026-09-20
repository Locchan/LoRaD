import subprocess
import time
from threading import Thread

from lorad.common.utils.logger import get_logger
from lorad.common.utils.misc import read_config

logger = get_logger()

PCM_SAMPLE_RATE = 44100
PCM_CHANNELS = 2
PCM_SAMPLE_BYTES = 2
PCM_FRAME_BYTES = PCM_CHANNELS * PCM_SAMPLE_BYTES
PCM_BYTES_PER_SEC = PCM_SAMPLE_RATE * PCM_FRAME_BYTES

# Content-Type / config names -> ffmpeg demuxers. "mpeg" from audio/mpeg is mp3, not MPEG-PS.
DEMUXERS = {
    "mp3": "mp3",
    "mpeg": "mp3",
    "mpeg3": "mp3",
    "x-mpeg": "mp3",
    "mpegurl": None,
    "aac": "aac",
    "aacp": "aac",
    "x-aac": "aac",
    "ogg": "ogg",
    "opus": "ogg",
    "vorbis": "ogg",
    "flac": "flac",
    "wav": "wav",
    "x-wav": "wav",
}


def demuxer_for(fmt):
    if not fmt:
        return None
    return DEMUXERS.get(str(fmt).strip().lower())


def decoder_label(fmt, bitrate_kbps=None) -> str:
    demuxer = demuxer_for(fmt)
    src = demuxer if demuxer else f"{fmt or 'unknown'} (probed)"
    if bitrate_kbps:
        src = f"{src} {int(bitrate_kbps)}k"
    return f"{src} -> PCM"


class Decoder:
    """One source (file/track/station) decoded to raw PCM. Short-lived: one per elementary stream."""

    def __init__(self, fmt, on_pcm, bitrate_kbps=None):
        self.fmt = fmt
        self.on_pcm = on_pcm
        self._stop = False
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
        demuxer = demuxer_for(fmt)
        if demuxer:
            command += ["-f", demuxer]
        else:
            # unknown/absent format: let ffmpeg probe, but do not wait long for it
            command += ["-probesize", "131072", "-analyzeduration", "0"]
        command += [
            "-i", "pipe:0",
            "-vn",
            "-f", "s16le",
            "-ar", str(PCM_SAMPLE_RATE),
            "-ac", str(PCM_CHANNELS),
            "pipe:1",
        ]
        logger.debug("Starting decoder: " + " ".join(command))
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        self.label = decoder_label(fmt, bitrate_kbps)
        logger.info(f"Starting ffmpeg [{self.process.pid}]: {self.label}")
        self.reader = Thread(name="Decoder", target=self._read_loop, daemon=True)
        self.reader.start()

    def alive(self):
        return self.process is not None and self.process.poll() is None

    def write(self, data: bytes) -> bool:
        if not data or self.process is None:
            return False
        try:
            self.process.stdin.write(data)
            self.process.stdin.flush()
            return True
        except Exception:
            return False

    def _read_loop(self):
        read_size = PCM_FRAME_BYTES * 2048
        while not self._stop:
            try:
                pcm = self.process.stdout.read(read_size)
            except Exception:
                break
            if not pcm:
                break
            self.on_pcm(pcm)

    def close(self, drain_timeout=3.0) -> bool:
        """Close the input and let the decoder flush what it already holds.

        Returns False if the decoder still had audio pending when the timeout ran out.
        """
        try:
            if self.process.stdin and not self.process.stdin.closed:
                self.process.stdin.close()
        except Exception:
            pass
        drained = True
        if self.reader.is_alive():
            self.reader.join(timeout=drain_timeout)
            drained = not self.reader.is_alive()
        self._stop = True
        pid = self.process.pid
        try:
            if self.alive():
                self.process.terminate()
                self.process.wait(timeout=1)
        except Exception:
            try:
                self.process.kill()
            except Exception:
                pass
        logger.info(f"Stopping ffmpeg [{pid}]: {self.label}" + ("" if drained else " (cut short)"))
        return drained


class Encoder:
    """The single long-lived PCM -> MP3 encoder. Never restarted for a source change."""

    def __init__(self, hub):
        self.hub = hub
        self.config = read_config()
        self.chunk_size = self.config["CHUNK_SIZE_KB"] * 1024
        self.process = None
        self.pump_thread = None
        self._stop_pump = False
        self.burst_done = False
        self.label = "PCM -> mp3"

    def alive(self):
        return self.process is not None and self.process.poll() is None

    def ensure(self):
        if self.alive():
            return
        if self.process is not None:
            logger.error("Encoder died, restarting it")
        self._start()

    def write(self, pcm: bytes) -> bool:
        self.ensure()
        try:
            self.process.stdin.write(pcm)
            self.process.stdin.flush()
            return True
        except Exception as e:
            logger.error(f"Can't feed the encoder: {e.__class__.__name__}")
            self._stop()
            return False

    def _start(self):
        self._stop()
        bitrate = self.config["BITRATE_KBPS"]
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-f", "s16le",
            "-ar", str(PCM_SAMPLE_RATE),
            "-ac", str(PCM_CHANNELS),
            "-i", "pipe:0",
            "-c:a", "libmp3lame",
            "-b:a", f"{bitrate}k",
            "-f", "mp3",
            "pipe:1",
        ]
        logger.debug("Starting: " + " ".join(command))
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        self.label = f"PCM -> mp3 {bitrate}k"
        logger.info(f"Starting ffmpeg [{self.process.pid}]: {self.label}")
        self.burst_done = False
        self._stop_pump = False
        self.pump_thread = Thread(name="Transcoder", target=self._pump, daemon=True)
        self.pump_thread.start()

    def _pump(self):
        process = self.process
        leftover = b""
        while not self._stop_pump and process.poll() is None:
            try:
                chunk = process.stdout.read(self.chunk_size)
            except Exception:
                break
            if not chunk:
                time.sleep(0.05)
                continue
            leftover += chunk
            if not self.burst_done:
                # give browsers a fat first blob so they do not stall on connect
                if len(leftover) >= self.chunk_size * 2:
                    self.hub.publish(leftover)
                    leftover = b""
                    self.burst_done = True
                continue
            while len(leftover) >= self.chunk_size:
                self.hub.publish(leftover[: self.chunk_size])
                leftover = leftover[self.chunk_size :]
        if leftover:
            self.hub.publish(leftover)

    def _stop(self):
        self._stop_pump = True
        if self.process is None:
            return
        pid = self.process.pid
        try:
            if self.process.stdin:
                self.process.stdin.close()
        except Exception:
            pass
        try:
            self.process.terminate()
            self.process.wait(timeout=2)
        except Exception:
            try:
                self.process.kill()
            except Exception:
                pass
        self.process = None
        logger.info(f"Stopping ffmpeg [{pid}]: {self.label}")
        if self.pump_thread is not None and self.pump_thread.is_alive():
            self.pump_thread.join(timeout=2)
        self.pump_thread = None
