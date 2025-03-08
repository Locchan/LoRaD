import os
from yandex_music import Client as YaMuClient, Track

from lorad.connectors.Connector import Connector
from lorad.connectors.yandex.Radio import Radio
from lorad.utils.logger import get_logger
from __main__ import TEMPDIR

logger = get_logger()

class YaMu(Connector):
    def __init__(self, token, bitrate):
        self.bitrate : int = bitrate
        self.client : YaMuClient = YaMuClient(token).init()
        self.radio : Radio = None
        self.radio_started : bool = False
        self.current_track : Track = None
        self.current_track_path : str = None
        self.current_track_name : str = None
        self.tracks_played : int = 0

    def initialize(self) -> Track:
        logger.info("Initializing Yandex Music...")
        if not self.radio_started:
            logger.info("Getting radio...")
            self.radio = Radio(self)
            self.radio.init_self_radio()
            track = self.radio.start_radio()
            self.radio_started = True
            self.__set_current_track(track)
            logger.info("Yandex Music initialized.")
            return track
        else:
            logger.warn("Radio is already started, but initialize was called. Returning current track...")
            return self.current_track

    def next_track(self):
        return self.__next_track()

    def __next_track(self) -> Track:
        if self.radio_started:
            track = self.radio.play_next()
        else:
            logger.warn("Radio was not started, but next_track was called. Starting radio...")
            track = self.start_radio()
        self.__set_current_track(track)
        return track

    def __download_current_track(self) -> str:
        if self.current_track is None:
            logger.error("Could not download track: No current track")
        else:
            self.tracks_played += 1
            self.current_track_path = os.path.join(TEMPDIR, f"current_yandex_{self.tracks_played}.mp3")

            # For debugging so that we don't download everytime we re-launch
            if not os.path.exists(self.current_track_path):
                logger.info(f"Downloading track [{self.current_track_name}] to {self.current_track_path}")
                self.current_track.download(filename=self.current_track_path, bitrate_in_kbps=self.bitrate)

    def __set_current_track(self, track) -> None:
        self.current_track = track
        artists = [x.name for x in self.current_track.artists]
        self.current_track_name = f"{','.join(artists)} - {self.current_track.title}"
        self.__download_current_track()

    def get_current_track_file(self):
        if self.current_track_path is None:
            logger.error("Could not get track: No current track path")
        else:
            return self.current_track_path