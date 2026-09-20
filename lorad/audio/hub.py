import threading
import time

from lorad.audio.sources.utils.Transcoder import (
    Decoder,
    Encoder,
    PCM_BYTES_PER_SEC,
    PCM_FRAME_BYTES,
)
from lorad.common.utils.logger import get_logger
from lorad.common.utils.priority import realtime_thread

logger = get_logger()

PCM_TICK_S = 0.02
PCM_BUFFER_S = 1.0
DRAIN_TIMEOUT_S = 120.0

_HUB = None


def _owner_name(owner):
    return getattr(owner, "name_tech", owner)


def get_hub():
    global _HUB
    if _HUB is None:
        _HUB = AudioHub()
    return _HUB


class AudioHub:
    """Exclusive audio bus.

    Owners feed encoded bytes of one source at a time. Every source gets its own decoder,
    so encoded frames of two sources are never spliced together. The encoder is long-lived
    and fed at exactly realtime, with silence when nothing is playing, so listeners always
    see one continuous MP3 stream no matter what changes upstream.
    """

    def __init__(self):
        # _state_lock is only ever held for a moment; _source_lock serializes the slow
        # source handovers. The clock thread must never wait on either of them.
        self._state_lock = threading.RLock()
        self._source_lock = threading.RLock()
        self._owner = None
        self._decoder = None

        self._cond = threading.Condition()
        self.latest = b""
        self.seq = 0

        self._pcm = bytearray()
        self._pcm_cv = threading.Condition()
        self._pcm_max = int(PCM_BYTES_PER_SEC * PCM_BUFFER_S)
        self._dropping = False
        self._audio_stream = None

        self.encoder = Encoder(self)
        threading.Thread(name="PcmClock", target=self._clock, daemon=True).start()

    # --- ownership -------------------------------------------------------

    def acquire(self, owner, input_format=None):
        with self._state_lock:
            prev = self._owner
            self._owner = owner
        if prev is not None and prev is not owner:
            logger.info(f"AudioHub: {_owner_name(prev)} yielding to {_owner_name(owner)}")
            try:
                prev.stop()
            except Exception as e:
                logger.warn(f"Previous owner stop failed: {e.__class__.__name__}")
        elif prev is None:
            # A program releases before handing back, so this is the other half of a handover.
            logger.info(f"AudioHub: {_owner_name(owner)} took the hub")
        if input_format is not None:
            self.begin_source(owner, input_format)

    def release(self, owner):
        with self._source_lock:
            with self._state_lock:
                if self._owner is not owner:
                    return
                self._owner = None
            logger.info(f"AudioHub: {_owner_name(owner)} released the hub")
            self._close_decoder(drain=False)

    def owner(self):
        return self._owner

    # --- source handling -------------------------------------------------

    def begin_source(self, owner, input_format="mp3", drain_previous=True, bitrate_kbps=None):
        """Start a new elementary stream (next track, next station, next program file).

        Draining waits until everything already decoded has been played, so a track is
        never cut short: feeding runs ahead of playback and that lead has to play out.
        """
        with self._source_lock:
            if self._owner is not owner:
                return False
            self._close_decoder(drain=drain_previous)
            if self._owner is not owner:
                return False
            with self._state_lock:
                self._decoder = Decoder(input_format, self._push_pcm, bitrate_kbps=bitrate_kbps)
            logger.debug(f"AudioHub: new source ({input_format})")
            return True

    def feed(self, owner, data: bytes) -> bool:
        with self._state_lock:
            if self._owner is not owner or self._decoder is None:
                return False
            decoder = self._decoder
        return decoder.write(data)

    def buffered_seconds(self) -> float:
        """Audio already decoded but not yet encoded, i.e. how far feeding runs ahead of listeners."""
        return len(self._pcm) / PCM_BYTES_PER_SEC

    def drop_buffered_audio(self):
        """Throw away decoded audio that has not been encoded yet (user-requested skips)."""
        with self._pcm_cv:
            self._pcm.clear()
            self._pcm_cv.notify_all()

    def _close_decoder(self, drain=True):
        with self._state_lock:
            decoder = self._decoder
            self._decoder = None
        if decoder is None:
            return
        if drain:
            # the clock keeps consuming meanwhile, so this returns once the tail has played
            if not decoder.close(drain_timeout=DRAIN_TIMEOUT_S):
                logger.warn("Timed out draining the previous source")
            return
        with self._pcm_cv:
            self._dropping = True
            self._pcm_cv.notify_all()
        try:
            decoder.close(drain_timeout=1.0)
        finally:
            with self._pcm_cv:
                self._dropping = False
                self._pcm_cv.notify_all()

    # --- PCM plumbing ----------------------------------------------------

    def _push_pcm(self, pcm: bytes):
        with self._pcm_cv:
            while len(self._pcm) + len(pcm) > self._pcm_max and not self._dropping:
                # backpressure: this is what paces the source feeding us
                self._pcm_cv.wait(0.25)
            if self._dropping:
                return
            self._pcm.extend(pcm)
            self._pcm_cv.notify_all()

    def _take_pcm(self, wanted: int):
        with self._pcm_cv:
            have = len(self._pcm)
            if have == 0 and not self._should_emit_silence():
                return None
            take = min(wanted, have)
            pcm = bytes(self._pcm[:take])
            del self._pcm[:take]
            self._pcm_cv.notify_all()
        if take < wanted:
            pcm += b"\x00" * (wanted - take)
        return pcm

    def _should_emit_silence(self):
        # deliberately lock-free: the clock must never block on a source handover
        if self._owner is not None:
            return True
        if self._audio_stream is None:
            from lorad.audio.server.AudioStream import AudioStream

            self._audio_stream = AudioStream
        return self._audio_stream.connected_clients > 0

    def _clock(self):
        realtime_thread()
        tick_bytes = int(PCM_BYTES_PER_SEC * PCM_TICK_S)
        tick_bytes -= tick_bytes % PCM_FRAME_BYTES
        next_tick = time.monotonic()
        while True:
            next_tick += PCM_TICK_S
            pcm = self._take_pcm(tick_bytes)
            if pcm is not None:
                self.encoder.write(pcm)
            delay = next_tick - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            else:
                next_tick = time.monotonic()

    # --- listeners -------------------------------------------------------

    def publish(self, chunk: bytes):
        if not chunk:
            return
        with self._cond:
            self.latest = chunk
            self.seq += 1
            self._cond.notify_all()

    def wait_chunk(self, last_seq: int, timeout=0.5):
        with self._cond:
            if self.seq == last_seq:
                self._cond.wait(timeout)
            return self.seq, self.latest
