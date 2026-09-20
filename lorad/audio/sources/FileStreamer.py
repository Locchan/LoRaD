import os
import time
from pathlib import Path
from threading import Thread

from mutagen.easyid3 import EasyID3

from lorad.audio.file_sources.FileRide import FileRide
from lorad.audio.hub import get_hub
from lorad.audio.ramfile import DoubleBuffer, file_duration_s, format_duration, format_slot_size
from lorad.audio.sources.GenericPlayer import GenericPlayer
from lorad.common.localization.localization import get_loc
from lorad.common.utils.logger import get_logger
import lorad.common.utils.globs as globs
from lorad.common.utils.misc import read_config
from lorad.common.utils.shm import PINNED_FALLBACK, read_yandex_stations, unlink_shm

logger = get_logger()

PREFETCH_BEFORE_S = 30


class FileStreamer(GenericPlayer):
    def __init__(self, connectors: list[FileRide], server=None):
        logger.debug("Initializing carousel...")
        config = read_config()
        self.name_readable = get_loc("PLAYER_NAME_FILESTREAMER")
        self.name_tech = "player_streaming"
        self.fallback_index = 0
        self.connectors = connectors
        self.connector_index = 0
        self.current_ride = self.connectors[self.connector_index]
        self.currently_playing = ""
        self.current_filepath = ""
        self.target_bitrate = int(config["BITRATE_KBPS"])
        self.bytes_per_sec = (self.target_bitrate * 1000) / 8
        self.feed_chunk = config["CHUNK_SIZE_KB"] * 1024
        self.running = False
        self._stop_current = False
        self.buffers = DoubleBuffer()
        self._skip_busy = False
        self._request_skip = False
        self._prefetching = False
        self._prefetch_epoch = 0
        self.switching = False
        self._track_started = 0.0
        self._track_duration = 0.0
        self._listen_open = False

    def supports_next_track(self) -> bool:
        return self.current_ride.supports_next_track()

    def track_length(self) -> float:
        # While a program owns the hub this player is stopped and its playhead is meaningless.
        if not self.running:
            return 0.0
        return self._track_duration or 0.0

    def track_position(self) -> float:
        """Seconds of the current track a listener has heard. Feeding runs ahead, so subtract the hub lead."""
        if not self._track_started:
            return 0.0
        elapsed = time.monotonic() - self._track_started - get_hub().buffered_seconds()
        if self._track_duration:
            elapsed = min(elapsed, self._track_duration)
        return max(elapsed, 0.0)

    def supports_liking(self) -> bool:
        return (
            self.current_ride is globs.YANDEX_OBJ
            and getattr(self.current_ride, "supports_liking", lambda: False)()
        )

    def current_track_liked(self) -> bool:
        if not self.supports_liking():
            raise RuntimeError("Current source does not support likes.")
        return self.current_ride.current_track_liked()

    def set_current_track_liked(self, liked: bool) -> bool:
        if not self.supports_liking():
            raise RuntimeError("Current source does not support likes.")
        return self.current_ride.set_current_track_liked(liked)

    def carousel(self):
        logger.debug("Entering carousel")
        hub = get_hub()
        while True:
            if not self.running:
                time.sleep(0.2)
                continue
            try:
                if not self.current_ride.initialized:
                    self.current_ride.initialize()
                track = self.current_ride.get_current_track()
                if not track or not isinstance(track, tuple):
                    raise RuntimeError(f"Got an invalid track for the carousel: '{track}'")
                self.currently_playing, self.current_filepath = track
                hub.acquire(self)
                self._play_from_file(self.current_filepath, self.currently_playing)
            except Exception as e:
                logger.warn(
                    f"Could not get the next track from {self.current_ride.__class__.__name__}: [{e.__class__.__name__}: {e}]"
                )
                self._play_fallback()
            self._rotate_connector()

    def _rotate_connector(self):
        if len(self.connectors) <= 1:
            return
        self.connector_index = (self.connector_index + 1) % len(self.connectors)
        self.current_ride = self.connectors[self.connector_index]

    def _play_fallback(self):
        logger.info("Loading fallback track.")
        fallback_dir = PINNED_FALLBACK
        fallback_tracks = os.listdir(fallback_dir)
        if len(fallback_tracks) == 0:
            logger.error("Nothing to fall back to! No fallback tracks! Catastrophe!")
            os._exit(1)
        if self.fallback_index >= len(fallback_tracks):
            self.fallback_index = 0
        path = os.path.join(fallback_dir, fallback_tracks[self.fallback_index])
        self.fallback_index += 1
        get_hub().acquire(self)
        self._play_from_file(path, None, allow_prefetch=False, advance_after=False, listen_report=False)

    def start(self):
        if self.running:
            logger.warn("Tried to start carousel when it is already started")
            return
        logger.info("Starting carousel")
        self._stop_current = False
        self.running = True
        get_hub().acquire(self)

    def stop(self):
        logger.info("Stopping carousel")
        self.running = False
        self._stop_current = True
        get_hub().release(self)

    def list_sources(self, cached=False):
        if globs.YANDEX_STATION_CACHE is not None:
            return globs.YANDEX_STATION_CACHE
        stations = read_yandex_stations()
        if stations is not None:
            globs.YANDEX_STATION_CACHE = stations
        return stations

    def current_source(self):
        radio = getattr(self.current_ride, "radio", None)
        if radio is None:
            return None
        return radio.station_id

    def switch_source(self, source_id):
        ride = self.current_ride
        if getattr(ride, "radio", None) is None:
            raise RuntimeError("Yandex is not initialized.")
        if self.switching:
            raise RuntimeError("A station switch is already in progress.")
        self.switching = True
        # The first track of the new station has to be downloaded; keep playing until it is here.
        Thread(name="StationSw", target=self._switch_worker, args=(ride, source_id), daemon=True).start()

    def _switch_worker(self, ride, source_id):
        try:
            with self.buffers.lock:
                # An in-flight prefetch must not land a track from the old station.
                self._prefetch_epoch += 1
                self.buffers.reserve_preload_for_track = True
                self.buffers.preload.clear()
            got = ride.switch_station(source_id)
            if not got:
                logger.error(f"Station switch failed: no playable track on {source_id}")
                return
            name, path = got
            self.buffers.load_preload_track(path, name)
            if not self.running:
                # Nothing is playing (a program owns the hub): the carousel will pick it up.
                ride.promote_next()
                return
            if not self._skip_to_preloaded():
                logger.error(f"Station switch to {source_id}: player did not take the new track")
        except Exception as e:
            logger.exception(e)
        finally:
            # If the new track never arrived, the current file still needs its windows.
            self.buffers.release_track_reservation()
            self.switching = False

    def set_track_name_from_metadata(self, path):
        try:
            track_id3_obj = EasyID3(path)
            artist = track_id3_obj.get("artist")
            title = track_id3_obj.get("title")
            if artist is None and title is None:
                raise RuntimeError("No track name in metadata.")
            return f"{artist} — {title}"
        except Exception:
            return Path(path).stem

    def play_files(self, files: dict[str, str], unswitcheable=False):
        """Play named files as hub owner (used by scheduled programs)."""
        hub = get_hub()
        hub.acquire(self)
        total = 0.0
        for path in files.values():
            if os.path.exists(path):
                total += file_duration_s(path)
        if unswitcheable and total > 0:
            from lorad.api.utils.misc import forbid_switching
            forbid_switching(int(total) + 1)
        was_running = self.running
        self.running = True
        self._stop_current = False
        try:
            for name, path in files.items():
                if not os.path.exists(path):
                    logger.error(f"Program file missing: {path}")
                    continue
                self._play_from_file(path, name, allow_prefetch=False, advance_after=False, listen_report=False)
                if self._stop_current:
                    break
        finally:
            self.running = was_running

    def skip_to_next(self) -> bool:
        if not self.supports_next_track():
            return False
        if self._skip_busy:
            return False
        self._skip_busy = True
        try:
            self._ensure_next_track_preloaded()
            deadline = time.time() + 180
            while time.time() < deadline:
                with self.buffers.lock:
                    if self.buffers.preload.ready and self.buffers.preload.kind == "track":
                        break
                    if self.buffers.preload.ready and self.buffers.preload.kind == "window":
                        self.buffers.preload.clear()
                time.sleep(0.2)
            else:
                logger.error("Skip failed: next track did not buffer in time")
                return False
            return self._skip_to_preloaded()
        finally:
            self._skip_busy = False

    def _skip_to_preloaded(self) -> bool:
        """Ask the feeding loop to cut over to whatever sits in the preload buffer."""
        self._request_skip = True
        waited = 0.0
        while self._request_skip and self.running and waited < 60:
            time.sleep(0.1)
            waited += 0.1
        if self._request_skip:
            self._request_skip = False
            return False
        return True

    def _ensure_next_track_preloaded(self):
        with self.buffers.lock:
            if self.buffers.preload.ready and self.buffers.preload.kind == "track":
                return
            self.buffers.preload.clear()
        self._prefetch_next_track()

    def _maybe_prefetch(self, seconds_left: float):
        # only the tail of the last window is worth prefetching: earlier windows still come from the same file
        if seconds_left > PREFETCH_BEFORE_S:
            return
        if self._prefetching or self.buffers.preload.ready:
            return
        if not self.buffers.current.is_last_window():
            return
        if not self.current_ride.supports_next_track():
            return
        logger.info(f"Prefetching the next track ({seconds_left:.0f}s left of the current one)")
        self._prefetch_next_track()

    def _prefetch_next_track(self):
        if self._prefetching:
            return
        if not self.current_ride.supports_next_track():
            return
        self._prefetching = True
        with self.buffers.lock:
            epoch = self._prefetch_epoch
            self.buffers.reserve_preload_for_track = True
            if self.buffers.preload.ready and self.buffers.preload.kind == "window":
                self.buffers.preload.clear()

        def work():
            try:
                got = self.current_ride.prefetch_next()
                if not got:
                    logger.warn("prefetch_next returned nothing")
                    return
                name, path = got
                if not path or not os.path.exists(path):
                    logger.warn("Prefetched track has no file")
                    return
                if epoch != self._prefetch_epoch:
                    logger.info(f"Dropping prefetched track from the previous station: {name}")
                    return
                self.buffers.load_preload_track(path, name)
                logger.info(
                    f"Next track buffered: {name} "
                    f"({format_slot_size(self.buffers.preload)}, {format_duration(self.buffers.preload.duration_s)})"
                )
            except Exception as e:
                logger.warn(f"Prefetch failed: {e.__class__.__name__}: {e}")
            finally:
                self._prefetching = False

        Thread(name="Prefetch", target=work, daemon=True).start()

    def _open_listen(self, listen_report: bool):
        if not listen_report:
            return
        self.current_ride.notify_playing()
        self._listen_open = True

    def _close_listen(self, skipped: bool = False):
        if not self._listen_open:
            return
        self._listen_open = False
        self.current_ride.notify_played(self.track_position(), skipped=skipped)

    def _play_from_file(self, path, name, allow_prefetch=True, advance_after=True, listen_report=True):
        if not name:
            name = self.set_track_name_from_metadata(path)
        self.currently_playing = name
        self.current_filepath = path
        self.buffers.load_current_track(path, name)
        if not self.buffers.current.ready:
            raise RuntimeError(f"Could not load {path} into RAM")
        self._track_started = time.monotonic()
        self._track_duration = self.buffers.current.duration_s or file_duration_s(path)
        logger.info(
            f"Playing from RAM: {name} "
            f"({format_slot_size(self.buffers.current)}, {format_duration(self._track_duration)})"
        )
        self._open_listen(listen_report)
        hub = get_hub()
        hub.begin_source(self, "mp3", bitrate_kbps=self.buffers.current.bitrate_kbps)
        try:
            while self.running and not self._stop_current:
                if self._request_skip:
                    if self.buffers.preload.ready and self.buffers.preload.kind == "track":
                        self._commit_next_track(user_skip=True, listen_report=listen_report)
                        self._request_skip = False
                        continue
                pos = 0
                data = self.buffers.current.data
                feed_rate = self._feed_rate()
                failures = 0
                while pos < len(data) and self.running and not self._stop_current and not self._request_skip:
                    chunk = data[pos : pos + self.feed_chunk]
                    # the hub paces us: feed() blocks once the decoded audio buffer is full
                    if not hub.feed(self, chunk):
                        failures += 1
                        if failures > 40:
                            raise RuntimeError("The hub is not accepting audio")
                        time.sleep(0.05)
                        continue
                    failures = 0
                    pos += len(chunk)
                    if allow_prefetch:
                        self._maybe_prefetch((len(data) - pos) / feed_rate)
                if self._request_skip:
                    continue
                if not self.running or self._stop_current:
                    break
                if self.buffers.preload.ready and self.buffers.preload.kind == "window":
                    # same file continues: keep the decoder, it is one elementary stream
                    self.buffers.swap()
                    continue
                if self.buffers.preload.ready and self.buffers.preload.kind == "track":
                    self._commit_next_track(listen_report=listen_report)
                    continue
                next_off = self.buffers.current.window_end()
                if next_off < self.buffers.current.file_size:
                    self.buffers.wait_preload(timeout=30)
                    if self.buffers.preload.ready and self.buffers.preload.kind == "window":
                        self.buffers.swap()
                        continue
                if self._prefetching:
                    # the download outlived the track: finish it here instead of restarting it in next_track()
                    logger.info("Track ended before its prefetch finished, waiting for the next track")
                    if self.buffers.wait_preload(timeout=60) and self.buffers.preload.kind == "track":
                        self._commit_next_track(listen_report=listen_report)
                        continue
                break
        finally:
            self._close_listen(skipped=False)
            if self.running and not self._stop_current and advance_after:
                finished = self.current_filepath
                self.current_ride.next_track()
                unlink_shm(finished)

    def _feed_rate(self) -> float:
        """Bytes per second this file is consumed at, for prefetch timing."""
        slot = self.buffers.current
        if slot.duration_s and slot.file_size:
            return slot.file_size / slot.duration_s
        return self.bytes_per_sec

    def _commit_next_track(self, user_skip=False, listen_report=True):
        self._close_listen(skipped=user_skip)
        name = self.buffers.preload.name
        path = self.buffers.preload.path
        finished = self.current_filepath
        hub = get_hub()
        if user_skip:
            hub.drop_buffered_audio()
        self.buffers.swap()
        hub.begin_source(self, "mp3", drain_previous=not user_skip, bitrate_kbps=self.buffers.current.bitrate_kbps)
        self.current_ride.promote_next()
        self.currently_playing = name
        self.current_filepath = path
        self._track_started = time.monotonic()
        self._track_duration = self.buffers.current.duration_s or file_duration_s(path)
        unlink_shm(finished)
        logger.info(
            f"Switched to buffered track: {name} "
            f"({format_slot_size(self.buffers.current)}, {format_duration(self._track_duration)})"
        )
        self._open_listen(listen_report)
