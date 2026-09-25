from random import random, shuffle

from yandex_music import Track

import lorad.common.utils.globs as globs
from lorad.common.utils.logger import get_logger

logger = get_logger()

PLAY_FROM = "desktop_win-home-playlist_of_the_day-playlist-default"


class Radio:
    def __init__(self, yamu_obj, station_id="user:onyourwave"):
        self.client = yamu_obj.client
        self.station_id = station_id
        self.station_from = None

        self.play_id = None
        self.index = 0
        self.current_track = None
        self.station_tracks = None
        self._listening_track = None
        self._listening_batch_id = None
        self._likes_queue: list[Track] = []

    def _is_likes(self) -> bool:
        return self.station_id == globs.YANDEX_STATION_LIKES

    def get_stations(self):
        return self.client.rotor_stations_list()

    def start_radio(self, station_id=None, station_from=None) -> Track | None:
        requested = station_id if station_id is not None else self.station_id
        if station_from is not None:
            self.station_from = station_from
        logger.info(f"Starting radio. Station: {requested}")
        if requested == globs.YANDEX_STATION_LIKES:
            queue = self._fetch_likes()
            if not queue:
                logger.warn("Liked songs station is empty; staying on the previous station")
                return None
            self.station_id = requested
            return self._start_likes(queue)
        self.station_id = requested
        self._likes_queue = []
        self.__update_radio_batch(None)
        self.current_track = self.__track_at_index()
        return self.current_track

    def play_next(self) -> Track | None:
        if self._is_likes():
            return self._likes_next()
        last_id = self.current_track.track_id if self.current_track is not None else None
        self.index += 1
        if self.station_tracks is None or self.index >= len(self.station_tracks.sequence):
            self.__update_radio_batch(last_id)
        self.current_track = self.__track_at_index()
        return self.current_track

    def drop_liked_track(self, track_id: str) -> None:
        if not self._is_likes() or not self._likes_queue:
            return
        current_id = self.current_track.track_id if self.current_track is not None else None
        self._likes_queue = [track for track in self._likes_queue if track.track_id != track_id]
        if not self._likes_queue:
            self.index = 0
            return
        if current_id and current_id != track_id:
            for idx, track in enumerate(self._likes_queue):
                if track.track_id == current_id:
                    self.index = idx
                    return
        self.index = min(self.index, len(self._likes_queue) - 1)

    def _start_likes(self, queue: list[Track] | None = None) -> Track | None:
        self.station_tracks = None
        self._likes_queue = queue if queue is not None else self._fetch_likes()
        if not self._likes_queue:
            logger.warn("Liked songs station is empty")
            self.current_track = None
            return None
        shuffle(self._likes_queue)
        self.index = 0
        self.current_track = self._likes_queue[0]
        return self.current_track

    def _likes_next(self) -> Track | None:
        if not self._likes_queue:
            return self._start_likes()
        self.index = (self.index + 1) % len(self._likes_queue)
        self.current_track = self._likes_queue[self.index]
        return self.current_track

    def _fetch_likes(self) -> list[Track]:
        try:
            likes = self.client.users_likes_tracks()
        except Exception as e:
            logger.warn(f"Could not load liked tracks: {e.__class__.__name__}: {e}")
            return []
        if likes is None:
            return []
        tracks = []
        try:
            fetched = likes.fetch_tracks() if hasattr(likes, "fetch_tracks") else None
        except Exception as e:
            logger.warn(f"Could not fetch liked tracks: {e.__class__.__name__}: {e}")
            fetched = None
        if fetched:
            tracks = [track for track in fetched if track is not None]
        else:
            ids = list(getattr(likes, "tracks_ids", []) or [])
            batch = 50
            for offset in range(0, len(ids), batch):
                chunk = ids[offset : offset + batch]
                try:
                    loaded = self.client.tracks(chunk)
                except Exception as e:
                    logger.warn(f"Could not fetch liked tracks: {e.__class__.__name__}: {e}")
                    continue
                tracks.extend(track for track in (loaded or []) if track is not None)
        return [track for track in tracks if getattr(track, "available", True)]

    def notify_play_start(self, track: Track):
        if track is None:
            return
        if self._is_likes():
            return
        if self._listening_track is not None:
            logger.debug("Yandex play start while a previous listen was still open")
        self.play_id = self.__generate_play_id()
        self._listening_track = track
        self._listening_batch_id = self.station_tracks.batch_id if self.station_tracks else None
        self.__send_play_audio(track, self.play_id, played_seconds=0, starting=True)
        self.__send_play_start_radio(track, self._listening_batch_id)

    def notify_play_end(self, track: Track, played_seconds: float, skipped: bool = False):
        if self._is_likes():
            return
        self._close_listen(track, played_seconds, skipped)

    def _close_listen(self, track: Track, played_seconds: float, skipped: bool):
        if self._listening_track is None or self.play_id is None:
            return
        ended = track if track is not None else self._listening_track
        play_id = self.play_id
        batch_id = self._listening_batch_id
        self.play_id = None
        self._listening_track = None
        self._listening_batch_id = None
        self.__send_play_audio(ended, play_id, played_seconds, starting=False)
        if skipped:
            self.__send_play_skip_radio(ended, played_seconds, batch_id)
        else:
            self.__send_play_end_radio(ended, played_seconds, batch_id)

    def __update_radio_batch(self, queue=None):
        self.index = 0
        self.station_tracks = self.client.rotor_station_tracks(self.station_id, queue=queue)
        self.__send_start_radio(self.station_tracks.batch_id)

    def __track_at_index(self) -> Track:
        return self.client.tracks([self.station_tracks.sequence[self.index].track.track_id])[0]

    def __send_start_radio(self, batch_id):
        self.client.rotor_station_feedback_radio_started(
            station=self.station_id, from_=self.station_from, batch_id=batch_id
        )

    def __album_id(self, track):
        if track.albums:
            return track.albums[0].id
        return 0

    def __duration_s(self, track) -> float:
        if not track or not track.duration_ms:
            return 0.0
        return track.duration_ms / 1000

    def __send_play_audio(self, track, play_id, played_seconds, starting: bool):
        total_seconds = self.__duration_s(track)
        played = 0.0 if starting else max(0.0, min(float(played_seconds), total_seconds or float(played_seconds)))
        payload = dict(
            from_=PLAY_FROM,
            track_id=track.id,
            album_id=self.__album_id(track),
            play_id=play_id,
            track_length_seconds=0 if starting else int(total_seconds),
            total_played_seconds=played,
            end_position_seconds=total_seconds,
        )
        logger.debug(
            f"Yandex play_audio {'start' if starting else 'end'}: "
            f"track={track.id} play_id={play_id} played={played:.1f}/{total_seconds:.1f}s"
        )
        try:
            self.client.play_audio(**payload)
        except Exception as e:
            logger.debug(f"Yandex play_audio failed: {e.__class__.__name__}: {e}")

    def __send_play_start_radio(self, track, batch_id):
        logger.debug(f"Yandex rotor trackStarted: track={track.id} batch={batch_id}")
        try:
            self.client.rotor_station_feedback_track_started(
                station=self.station_id, track_id=track.id, batch_id=batch_id
            )
        except Exception as e:
            logger.debug(f"Yandex rotor trackStarted failed: {e.__class__.__name__}: {e}")

    def __send_play_end_radio(self, track, played_seconds, batch_id):
        played = max(0.0, float(played_seconds))
        logger.debug(
            f"Yandex rotor trackFinished: track={track.id} played={played:.1f}s batch={batch_id}"
        )
        try:
            self.client.rotor_station_feedback_track_finished(
                station=self.station_id,
                track_id=track.id,
                total_played_seconds=played,
                batch_id=batch_id,
            )
        except Exception as e:
            logger.debug(f"Yandex rotor trackFinished failed: {e.__class__.__name__}: {e}")

    def __send_play_skip_radio(self, track, played_seconds, batch_id):
        played = max(0.0, float(played_seconds))
        logger.debug(f"Yandex rotor skip: track={track.id} played={played:.1f}s batch={batch_id}")
        try:
            self.client.rotor_station_feedback_skip(
                station=self.station_id,
                track_id=track.id,
                total_played_seconds=played,
                batch_id=batch_id,
            )
        except Exception as e:
            logger.debug(f"Yandex rotor skip failed: {e.__class__.__name__}: {e}")

    @staticmethod
    def __generate_play_id():
        return "%s-%s-%s" % (int(random() * 1000), int(random() * 1000), int(random() * 1000))
