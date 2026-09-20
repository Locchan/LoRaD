import os
import time
from threading import RLock, Thread
from yandex_music import Client as YaMuClient, Track
import yandex_music
import hashlib

import lorad.common.utils.globs as globs
from lorad.audio.file_sources.FileRide import FileRide
from lorad.audio.file_sources.yandex.Radio import Radio
from lorad.common.utils.logger import get_logger
from lorad.common.utils.shm import read_yandex_stations, unlink_shm, write_yandex_stations

logger = get_logger()


class YaMu(FileRide):
    def __init__(self, token, bitrate):
        super().__init__()
        self.bitrate: int = bitrate
        self.client: YaMuClient = YaMuClient(token).init()
        self.radio: Radio = None
        self.radio_started: bool = False
        self.current_track: Track = None
        self.current_track_path: str = None
        self.current_track_name: str = None
        self.next_track_obj: Track = None
        self.next_track_path: str = None
        self.next_track_name: str = None
        self._likes_lock = RLock()
        self._liked_track_ids: set[str] | None = None

    def cache_stations_async(self) -> None:
        """Warm the station cache off the boot path; the pinned copy serves until it lands."""
        pinned = read_yandex_stations()
        if pinned:
            globs.YANDEX_STATION_CACHE = pinned
            logger.info(f"Serving {len(pinned)} Yandex stations from shm while refreshing")
        Thread(name="YaStations", target=self.cache_stations, daemon=True).start()

    def cache_stations(self) -> dict | None:
        """Fetch Yandex rotor stations once and pin the map in shm for the API."""
        try:
            stations = self._station_map(self.client.rotor_stations_list())
            write_yandex_stations(stations)
            globs.YANDEX_STATION_CACHE = stations
            logger.info(f"Pinned {len(stations)} Yandex stations in shm")
            return stations
        except Exception as e:
            logger.exception(e)
            existing = read_yandex_stations()
            if existing:
                globs.YANDEX_STATION_CACHE = existing
                logger.warning(f"Using previously pinned Yandex stations ({len(existing)})")
                return existing
            return None

    @staticmethod
    def _station_map(raw) -> dict:
        stations = {}
        for astation in raw:
            stations[astation["station"]["name"]] = (
                f"{astation['station']['id']['type']}:{astation['station']['id']['tag']}"
            )
        return stations

    def initialize(self) -> Track:
        logger.info("Initializing Yandex Music...")
        if not self.radio_started:
            logger.info("Getting radio...")
            self.radio = Radio(self)
            track = self.radio.start_radio()
            self.radio_started = True
            self.__set_current_track(track)
            logger.info("Yandex Music initialized.")
            self.initialized = True
            return track
        logger.warn("Radio is already started, but initialize was called. Returning current track...")
        return self.current_track

    def next_track(self):
        if self.next_track_obj is not None:
            self.promote_next()
            if self.current_track_path:
                return self.current_track
        track = self.__advance()
        self.__set_current_track(track)
        return track

    def switch_station(self, station_id):
        """Start the new station and download its first track as the next one, so the
        player can cut over from what it is already playing."""
        if self.radio is None:
            raise RuntimeError("Yandex is not initialized.")
        # Whatever was prefetched belongs to the old station.
        self.drop_prefetched()
        track = self.radio.start_radio(station_id)
        self.radio_started = True
        self.__set_next_track(track)
        if not self.next_track_path:
            return None
        return self.next_track_name, self.next_track_path

    def drop_prefetched(self):
        if self.next_track_path:
            unlink_shm(self.next_track_path)
        self.next_track_obj = None
        self.next_track_path = None
        self.next_track_name = None

    def supports_next_track(self) -> bool:
        return True

    def supports_liking(self) -> bool:
        return self.current_track is not None

    def current_track_liked(self) -> bool:
        with self._likes_lock:
            if self.current_track is None:
                return False
            if self._liked_track_ids is None:
                liked = self.client.users_likes_tracks()
                self._liked_track_ids = set(liked.tracks_ids if liked is not None else [])
            return self.current_track.track_id in self._liked_track_ids

    def set_current_track_liked(self, liked: bool) -> bool:
        with self._likes_lock:
            if self.current_track is None:
                raise RuntimeError("No Yandex track is currently playing.")
            track_id = self.current_track.track_id
            if self._liked_track_ids is not None:
                already_liked = track_id in self._liked_track_ids
                if already_liked == liked:
                    return liked
            if liked:
                changed = self.client.users_likes_tracks_add(track_id)
            else:
                changed = self.client.users_likes_tracks_remove(track_id)
            if not changed:
                raise RuntimeError("Yandex Music rejected the like change.")
            if self._liked_track_ids is None:
                self._liked_track_ids = set()
            if liked:
                self._liked_track_ids.add(track_id)
            else:
                self._liked_track_ids.discard(track_id)
            logger.info(
                f"Yandex track {'liked' if liked else 'unliked'}: {self.current_track_name}"
            )
            return liked

    def prefetch_next(self):
        if self.next_track_obj is not None:
            self.next_track_path = self._ensure_downloaded(
                self.next_track_obj, self.next_track_name, self.next_track_path
            )
            if self.next_track_path:
                return self.next_track_name, self.next_track_path
        track = self.__advance()
        self.__set_next_track(track)
        if self.next_track_path:
            return self.next_track_name, self.next_track_path
        return None

    def promote_next(self):
        if self.next_track_obj is None:
            return
        self.next_track_path = self._ensure_downloaded(
            self.next_track_obj, self.next_track_name, self.next_track_path
        )
        if not self.next_track_path:
            return
        self.current_track = self.next_track_obj
        self.current_track_path = self.next_track_path
        self.current_track_name = self.next_track_name
        self.next_track_obj = None
        self.next_track_path = None
        self.next_track_name = None

    def notify_playing(self):
        if self.radio is None or self.current_track is None:
            return
        self.radio.notify_play_start(self.current_track)

    def notify_played(self, played_seconds: float, skipped: bool = False):
        if self.radio is None or self.current_track is None:
            return
        self.radio.notify_play_end(self.current_track, played_seconds, skipped=skipped)

    def __advance(self) -> Track:
        if self.radio_started:
            return self.radio.play_next()
        logger.warn("Radio was not started, but next_track was called. Starting radio...")
        return self.radio.start_radio()

    def __download_track(self, track, name) -> str | None:
        try:
            if globs.FLG_NO_DOWNLOADING in globs.FEATURE_FLAGS:
                raise RuntimeError("NO_DOWNLOADING flag is set.")
            if track is None:
                logger.error("Could not download track: No current track")
                return None
            track_hash = hashlib.md5(name.encode("utf-8")).hexdigest()
            path = os.path.join(globs.TEMPDIR, f"yandex_{track_hash}.mp3")
            if not os.path.exists(path):
                logger.info(f"Downloading track [{name}]")
                started = time.monotonic()
                partial_path = path + ".part.mp3"
                unlink_shm(partial_path)
                try:
                    track.download(filename=partial_path, bitrate_in_kbps=self.bitrate)
                except yandex_music.exceptions.InvalidBitrateError:
                    unlink_shm(partial_path)
                    max_avail_bitrate = max(
                        track.get_download_info(), key=lambda item: item.bitrate_in_kbps
                    ).bitrate_in_kbps
                    logger.warn(
                        f"Could not download the track with correct bitrate. Falling back to {max_avail_bitrate} (highest available)."
                    )
                    track.download(filename=partial_path, bitrate_in_kbps=max_avail_bitrate)
                os.replace(partial_path, path)
                logger.info(
                    f"Downloaded [{name}]: {os.path.getsize(path) / (1024 * 1024):.2f} MB "
                    f"in {time.monotonic() - started:.1f}s"
                )
            else:
                logger.info(f"Track [{name}] is already downloaded, reusing it")
            return path
        except RuntimeError as e:
            logger.warning(f"Track download cancelled: {e}")
            return None
        except Exception:
            if "partial_path" in locals():
                unlink_shm(partial_path)
            raise

    def __track_name(self, track) -> str:
        artists = [x.name for x in track.artists]
        return f"{','.join(artists)} - {track.title}"

    def __set_current_track(self, track) -> None:
        self.current_track = track
        self.current_track_name = self.__track_name(track)
        self.current_track_path = self.__download_track(track, self.current_track_name)

    def __set_next_track(self, track) -> None:
        self.next_track_obj = track
        self.next_track_name = self.__track_name(track)
        self.next_track_path = self.__download_track(track, self.next_track_name)

    def get_current_track(self) -> tuple[str, str]:
        if self.current_track is None:
            logger.error("Could not get track: No current track")
            return None
        self.current_track_path = self._ensure_downloaded(
            self.current_track, self.current_track_name, self.current_track_path
        )
        if not self.current_track_path:
            logger.error("Could not get track: No current track path")
            return None
        return self.current_track_name, self.current_track_path

    def _ensure_downloaded(self, track, name, path) -> str | None:
        if path and os.path.exists(path):
            return path
        if path:
            logger.info(f"Track file gone from shm, re-downloading: {name}")
        return self.__download_track(track, name)
