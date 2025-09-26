import time
import math
import os
from pathlib import Path
from time import sleep
from typing import Tuple

from lorad.audio.file_sources.FileRide import FileRide
from lorad.audio.server.AudioStream import AudioStream
from lorad.audio.sources.utils.Transcoder import Transcoder
from lorad.common.localization.localization import get_loc
from lorad.common.utils.globs import END_OF_TRANSCODED_DATA
from lorad.common.utils.logger import get_logger
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3

from lorad.common.utils.misc import read_config

logger = get_logger()

# Supports only mp3 as it's hardcoded in the Transcoder class creation and was default since the first attempts at this project.
class FileStreamer:
    def __init__(self, connectors: list[FileRide], server: AudioStream):
        logger.debug("Initializing carousel...")
        config = read_config()
        self.name_readable = get_loc("PLAYER_NAME_FILESTREAMER")
        self.name_tech = "player_streaming"
        self.fallback_index = 0
        self.server = server
        self.connectors = connectors
        self.connector_index = 0
        self.current_ride = self.connectors[self.connector_index]
        self.carousel_enabled = False
        self.chunk_size = config["CHUNK_SIZE_KB"]
        self.chunk_size_bytes = self.chunk_size * 102
        self.currently_playing = ""
        self.current_filepath = ""
        self.transcoder : Transcoder | None = None
        self.target_bitrate = int(config["BITRATE_KBPS"])
        self.default_format = config["DEFAULT_AUDIO_FORMAT"]
        self.running = False
        self.free = True
        self.initial_burst_chunks = 8

    def carousel(self):
        logger.debug("Entering carousel")
        while True:
            if self.carousel_enabled:
                try:
                    if not self.current_ride.initialized:
                        self.current_ride.initialize()
                    track = self.current_ride.get_current_track()
                    if track is not None and track and isinstance(track, Tuple):
                        (self.currently_playing, self.current_filepath) = track
                    else:
                        raise RuntimeError(f"Got an invalid track for the carousel: '{track}' Falling back")
                    # Serve chunks and exit when the end of the file is reached
                    self.serve_file()
                    self.cleanup()
                    self.current_ride.next_track()
                except Exception as e:
                    logger.warn(f"Could not get the next track from {self.current_ride.__class__.__name__}: [{e.__class__.__name__}: {e}]")
                    self.stop_carousel()
                    self.fallback()
                # Rotating connectors if possible
                self.connector_index += 1
                if len(self.connectors) > self.connector_index:
                    self.current_ride = self.connectors[self.connector_index]
                else:
                    self.current_ride = self.connectors[0]
            else:
                sleep(1)

    def fallback(self):
        logger.info("Loading fallback track.")
        config = read_config()
        fallback_tracks = os.listdir(config["FALLBACK_TRACK_DIR"])
        if len(fallback_tracks) == 0:
            logger.error("Nothing to fall back to! No fallback tracks! Catastrophe!")
            os._exit(1)
        if self.fallback_index == len(fallback_tracks):
            self.fallback_index = 0
        self.serve_file(os.path.join(config["FALLBACK_TRACK_DIR"], fallback_tracks[self.fallback_index]))
        if self.carousel_enabled:
            self.fallback_index += 1
            self.start_carousel()

    def start(self):
        self.start_carousel()

    def stop(self):
        self.stop_carousel()

    def start_carousel(self):
        if self.carousel_enabled:
            logger.warn("Tried to start carousel when it is already started")
        else:
            logger.info("Starting carousel")
            self.carousel_enabled = True

    def stop_carousel(self):
        if not self.carousel_enabled:
            logger.warn("Tried to stop carousel when it is already stopped")
        logger.info("Stopping carousel")
        self.running = False
        self.carousel_enabled = False

    # If we don't have track name from whoever wants us to play it, try getting it from metadata.
    # If even this fails, just cut the file extension use the rest as the track title
    def set_track_name_from_metadata(self):
        try:
            track_id3_obj = EasyID3(self.current_filepath)
            artist = track_id3_obj.get("artist")
            title = track_id3_obj.get("title")
            if artist is None and title is None:
                raise RuntimeError("No track name in metadata.")
            self.currently_playing = f"{artist} — {title}"
        except Exception:
            self.currently_playing = Path(self.current_filepath).stem

    def get_track_info(self) -> tuple:
        track_info = MP3(self.current_filepath).info
        source_bitrate = track_info.bitrate / 1000
        seconds_per_chunk = self.chunk_size_bytes / ( (source_bitrate * 1000) / 8)
        logger.debug(f"Seconds per chunk: {seconds_per_chunk}")
        logger.info(f"Starting to serve the next track...")
        logger.info(f"Track duration: {track_info.length}s")
        return source_bitrate, seconds_per_chunk, track_info.length

    def serve_file(self, track_filepath=None, track_name=None, unswitcheable=False):
        if track_filepath is not None:
            self.current_filepath = track_filepath
        if track_name is not None:
            self.currently_playing = track_name
        # Wait if some other thread is in here
        while True:
            if not self.free:
                sleep(1)
                logger.warning("Waiting until another thread frees the stream...")
            else:
                break

        self.running = True
        self.free = False
        try:
            if self.currently_playing == "":
                self.set_track_name_from_metadata()

            source_bitrate, seconds_per_chunk, length = self.get_track_info()
            if unswitcheable:
                from lorad.api.utils.misc import forbid_switching
                forbid_switching(length)

            self.transcoder = Transcoder(input_format="mp3", respect_chunk_size=True)

            with open(self.current_filepath, 'rb') as mp3file:
                self.transcoder.start()
                data_accepted = True
                while True:
                    if self.running:
                        # AudioStream will refuse data if no one is listening.
                        if data_accepted:
                            source_chunk = mp3file.read(self.chunk_size_bytes)
                            if not source_chunk:
                                self.transcoder.no_more_data = True
                            else:
                                self.transcoder.add_data(source_chunk)
                            transcoder_chunk = self.transcoder.get_transcoded_chunk()
                            if transcoder_chunk is None:
                                logger.error("Transcoder error. See logs!")
                                self.transcoder.stop()
                                return
                            elif not transcoder_chunk:
                                pass
                            elif transcoder_chunk == END_OF_TRANSCODED_DATA:
                                self.transcoder.stop()
                                return
                            else:
                                data_accepted = AudioStream.add_data(transcoder_chunk, only_if_listeners_there=True)
                        else:
                            data_accepted = AudioStream.add_data(transcoder_chunk, only_if_listeners_there=True)
                    else:
                        self.transcoder.stop()
                        break
                    time.sleep(seconds_per_chunk)
        finally:
            logger.info("Exiting file playback method.")
            self.free = True
            AudioStream.track_ended = True

    def cleanup(self):
        if os.path.exists(self.current_filepath):
            pass
            #os.remove(self.current_filepath)