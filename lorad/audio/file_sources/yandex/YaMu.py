import os
import time
from threading import RLock, Thread
from yandex_music import Client as YaMuClient, Track
import yandex_music
import hashlib

import lorad.common.utils.globs as globs
from lorad.audio.file_sources.FileRide import FileRide
from lorad.audio.file_sources.yandex import covers as yandex_covers
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
        self.current_track_title: str = None
        self.current_track_artist: str = None
        self.next_track_obj: Track = None
        self.next_track_path: str = None
        self.next_track_name: str = None
        self.next_track_title: str = None
        self.next_track_artist: str = None
        self.custom_queue: list[Track] = []
        self.playing_custom: bool = False
        self._next_is_custom: bool = False
        self._likes_lock = RLock()
        self._liked_track_ids: set[str] | None = None

    def cache_stations_async(self) -> None:
        """Warm the station cache off the boot path; the pinned copy serves until it lands."""
        pinned = read_yandex_stations()
        if pinned:
            globs.YANDEX_STATION_CACHE = self._with_synthetic(pinned)
            logger.info(f"Serving {len(globs.YANDEX_STATION_CACHE)} Yandex stations from shm while refreshing")
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
                stations = self._with_synthetic(existing)
                globs.YANDEX_STATION_CACHE = stations
                logger.warning(f"Using previously pinned Yandex stations ({len(stations)})")
                return stations
            fallback = self._with_synthetic({})
            globs.YANDEX_STATION_CACHE = fallback
            return fallback

    @staticmethod
    def _with_synthetic(stations: dict) -> dict:
        """Synthetic stations lead, in their own order; the rotor list follows, sorted by name."""
        synthetic_ids = set(globs.YANDEX_SYNTHETIC_STATIONS.values())
        # A pinned map already carries the synthetic pair, so drop it before re-adding
        rest = {
            name: tech
            for name, tech in stations.items()
            if name not in globs.YANDEX_SYNTHETIC_STATIONS and tech not in synthetic_ids
        }
        merged = dict(globs.YANDEX_SYNTHETIC_STATIONS)
        for name in sorted(rest, key=str.casefold):
            merged[name] = rest[name]
        return merged

    @classmethod
    def _station_map(cls, raw) -> dict:
        stations = {}
        for astation in raw:
            stations[astation["station"]["name"]] = (
                f"{astation['station']['id']['type']}:{astation['station']['id']['tag']}"
            )
        return cls._with_synthetic(stations)

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
        if self.custom_queue:
            track = self.custom_queue.pop(0)
            self._next_is_custom = True
            self.__set_current_track(track)
            self.playing_custom = True
            self._next_is_custom = False
            return self.current_track
        self.playing_custom = False
        track = self.__advance()
        self.__set_current_track(track)
        return track

    def switch_station(self, station_id):
        """Start the new station and download its first track as the next one, so the
        player can cut over from what it is already playing."""
        if self.radio is None:
            raise RuntimeError("Yandex is not initialized.")
        # Whatever was prefetched belongs to the old station.
        self.clear_custom_playlist()
        self.drop_prefetched()
        track = self.radio.start_radio(station_id)
        if track is None:
            return None
        self.radio_started = True
        self._next_is_custom = False
        self.__set_next_track(track)
        if not self.next_track_path:
            return None
        return self.next_track_name, self.next_track_path

    def clear_custom_playlist(self):
        self.custom_queue.clear()
        self.playing_custom = False
        self._next_is_custom = False

    def drop_prefetched(self):
        if self.next_track_path:
            unlink_shm(self.next_track_path)
        self.next_track_obj = None
        self.next_track_path = None
        self.next_track_name = None
        self.next_track_title = None
        self.next_track_artist = None
        self._next_is_custom = False

    def search_tracks(self, query: str, limit: int = 10) -> list[dict]:
        """Top track hits for the UI dropdown: id / title / artist."""
        text = (query or "").strip()
        if not text:
            return []
        result = self.client.search(text, type_="track")
        if result is None or result.tracks is None or not result.tracks.results:
            return []
        found = []
        for track in result.tracks.results[: max(0, int(limit))]:
            artist, title, _ = self.__track_parts(track)
            found.append(
                {
                    "id": str(track.track_id),
                    "title": title,
                    "artist": artist,
                }
            )
        return found

    def queue_track(self, track_id: str, *, start_custom: bool = False) -> tuple[str, str] | None:
        """Download a specific track as next. start_custom clears the custom playlist."""
        if self.radio is None:
            raise RuntimeError("Yandex is not initialized.")
        track_id = str(track_id or "").strip()
        if not track_id:
            return None
        if start_custom:
            self.custom_queue.clear()
        self.drop_prefetched()
        tracks = self.client.tracks(track_id)
        if not tracks:
            logger.warning(f"Yandex track not found: {track_id}")
            return None
        track = tracks[0]
        artist, title, name = self.__track_parts(track)
        path = self.__download_track(track, name)
        if not path:
            return None
        self.next_track_obj = track
        self.next_track_name = name
        self.next_track_path = path
        self.next_track_title = title
        self.next_track_artist = artist
        self._next_is_custom = True if start_custom else self.playing_custom
        yandex_covers.ensure_cover_async(track)
        return name, path

    def enqueue_custom_track(self, track_id: str) -> bool:
        """Append metadata to the custom playlist. Download happens later via prefetch."""
        if not self.playing_custom:
            return False
        track_id = str(track_id or "").strip()
        if not track_id:
            return False
        tracks = self.client.tracks(track_id)
        if not tracks:
            logger.warning(f"Yandex track not found: {track_id}")
            return False
        self.custom_queue.append(tracks[0])
        logger.info(
            f"Queued custom Yandex track [{self.__track_parts(tracks[0])[2]}] "
            f"(queue={len(self.custom_queue)})"
        )
        # Drop a station prefetch so the custom queue is what Prefetch pulls next.
        if self.next_track_obj is not None and not self._next_is_custom:
            self.drop_prefetched()
        return True

    def is_playing_custom(self) -> bool:
        return bool(self.playing_custom)

    def custom_queue_list(self) -> list[dict]:
        """Current custom track (if any) plus upcoming (buffered next + queued)."""
        items = []
        if self.playing_custom and self.current_track is not None:
            artist, title, _ = self.__track_parts(self.current_track)
            items.append({"artist": artist, "title": title, "playing": True})
        if self._next_is_custom and self.next_track_obj is not None:
            artist, title, _ = self.__track_parts(self.next_track_obj)
            items.append({"artist": artist, "title": title, "playing": False})
        for track in self.custom_queue:
            artist, title, _ = self.__track_parts(track)
            items.append({"artist": artist, "title": title, "playing": False})
        return items

    def remove_custom_queue_at(self, index: int) -> bool:
        """Remove an upcoming custom entry by the same index as custom_queue_list()."""
        if not self.playing_custom or index < 0:
            return False
        # Skip the currently playing row — it is not removable from the queue UI.
        if self.playing_custom and self.current_track is not None:
            if index == 0:
                return False
            index -= 1
        if self._next_is_custom and self.next_track_obj is not None:
            if index == 0:
                self.drop_prefetched()
                return True
            index -= 1
        if index < len(self.custom_queue):
            removed = self.custom_queue.pop(index)
            logger.info(
                f"Removed custom Yandex track [{self.__track_parts(removed)[2]}] "
                f"(queue={len(self.custom_queue)})"
            )
            return True
        return False

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
                radio = self.radio
                if radio is not None and radio.station_id == globs.YANDEX_STATION_LIKES:
                    radio.drop_liked_track(track_id)
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
        if self.custom_queue:
            track = self.custom_queue.pop(0)
            self._next_is_custom = True
            self.__set_next_track(track)
            if self.next_track_path:
                return self.next_track_name, self.next_track_path
            return None
        self._next_is_custom = False
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
        self.current_track_title = self.next_track_title
        self.current_track_artist = self.next_track_artist
        self.playing_custom = bool(self._next_is_custom)
        self.next_track_obj = None
        self.next_track_path = None
        self.next_track_name = None
        self.next_track_title = None
        self.next_track_artist = None
        self._next_is_custom = False
        yandex_covers.ensure_cover_async(self.current_track)

    def current_cover_ready(self) -> bool:
        if self.current_track is None:
            return False
        track_id = self.current_track.track_id
        if yandex_covers.cover_ready(track_id):
            return True
        yandex_covers.ensure_cover_async(self.current_track)
        return False

    def current_cover_bytes(self) -> bytes | None:
        if self.current_track is None:
            return None
        data = yandex_covers.read_cover_bytes(self.current_track.track_id)
        if data:
            return data
        yandex_covers.ensure_cover_async(self.current_track)
        return None

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

    def __track_parts(self, track) -> tuple[str, str, str]:
        """(artist, title, combined display name)."""
        if track is None:
            return "", "unknown", "unknown"
        artists = ", ".join(x.name for x in (track.artists or []) if x.name)
        title = track.title or "unknown"
        if artists:
            return artists, title, f"{artists} - {title}"
        return "", title, title

    def __apply_track(self, track, as_next: bool) -> bool:
        retries = 16 if self.radio is not None and self.radio._is_likes() else 1
        current = track
        for _ in range(max(1, retries)):
            if current is None:
                break
            artist, title, name = self.__track_parts(current)
            path = self.__download_track(current, name)
            if path:
                if as_next:
                    self.next_track_obj = current
                    self.next_track_name = name
                    self.next_track_path = path
                    self.next_track_title = title
                    self.next_track_artist = artist
                else:
                    self.current_track = current
                    self.current_track_name = name
                    self.current_track_path = path
                    self.current_track_title = title
                    self.current_track_artist = artist
                yandex_covers.ensure_cover_async(current)
                return True
            if retries == 1:
                break
            current = self.radio.play_next()
        if as_next:
            self.next_track_obj = None
            self.next_track_name = None
            self.next_track_path = None
            self.next_track_title = None
            self.next_track_artist = None
        else:
            self.current_track = None
            self.current_track_name = None
            self.current_track_path = None
            self.current_track_title = None
            self.current_track_artist = None
        return False

    def __set_current_track(self, track) -> None:
        self.__apply_track(track, as_next=False)

    def __set_next_track(self, track) -> None:
        self.__apply_track(track, as_next=True)

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
