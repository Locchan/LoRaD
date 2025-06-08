import os
from yandex_music import Client as YaMuClient, Track
import yandex_music
import hashlib

import lorad.common.utils.globs as globs
from lorad.radio.sources.FileRide import FileRide
from lorad.radio.sources.yandex.Radio import Radio
from lorad.common.utils.logger import get_logger

logger = get_logger()

class YaMu(FileRide):
    def __init__(self, token, bitrate):
        super().__init__()
        self.bitrate : int = bitrate
        self.client : YaMuClient = YaMuClient(token).init()
        self.radio : Radio = None
        self.radio_started : bool = False
        self.current_track : Track = None
        self.current_track_path : str = None
        self.current_track_name : str = None

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
        else:
            logger.warn("Radio is already started, but initialize was called. Returning current track...")
            return self.current_track

    def next_track(self):
        return self.__next_track()

    # TODO: Add support for non-radio tracklists (charts, playlists)
    def __next_track(self) -> Track:
        if self.radio_started:
            track = self.radio.play_next()
        else:
            logger.warn("Radio was not started, but next_track was called. Starting radio...")
            track = self.radio.start_radio()
        self.__set_current_track(track)
        return track

    def __download_current_track(self) -> str:
        try:
            if globs.FLG_NO_DOWNLOADING in globs.FEATURE_FLAGS:
                raise RuntimeError("NO_DOWNLOADING flag is set.")
            if self.current_track is None:
                logger.error("Could not download track: No current track")
            else:
                track_hash = hashlib.md5(self.current_track_name.encode('utf-8')).hexdigest()
                self.current_track_path = os.path.join(globs.TEMPDIR, f"yandex_{track_hash}.mp3")

                # For debugging so that we don't download everytime we re-launch
                if not os.path.exists(self.current_track_path):
                    logger.debug(f"Downloading track [{self.current_track_name}]")
                    try:
                        self.current_track.download(filename=self.current_track_path, bitrate_in_kbps=self.bitrate)
                    except yandex_music.exceptions.InvalidBitrateError:
                        max_avail_bitrate = max(self.current_track.get_download_info(), key=lambda item: item.bitrate_in_kbps).bitrate_in_kbps
                        logger.warn(f"Could not download the track with correct bitrate. Falling back to {max_avail_bitrate} (highest available).")
                        self.current_track.download(filename=self.current_track_path, bitrate_in_kbps=max_avail_bitrate)
        except RuntimeError as e:
            logger.warning(f"Track download cancelled: {e}")

    def __set_current_track(self, track) -> None:
        self.current_track = track
        artists = [x.name for x in self.current_track.artists]
        self.current_track_name = f"{','.join(artists)} - {self.current_track.title}"
        self.__download_current_track()

    def get_current_track(self) -> tuple[str, str]:
        if self.current_track_path is None:
            logger.error("Could not get track: No current track path")
        else:
            return self.current_track_name, self.current_track_path