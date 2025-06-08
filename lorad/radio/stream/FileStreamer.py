from collections import deque
import datetime
import math
import os
from pathlib import Path
from time import sleep
from typing import Tuple

from openai.types.beta.threads import Run
from lorad.radio.sources.FileRide import FileRide
from lorad.radio.server.LoRadSrv import LoRadServer
from lorad.common.utils.logger import get_logger
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3

from lorad.common.utils.misc import read_config

logger = get_logger()

class FileStreamer():
    def __init__(self, connectors: list[FileRide], server: LoRadServer):
        logger.debug("Initializing carousel...")
        config = read_config()
        self.fallback_index = 0
        self.server = server
        self.connectors = connectors
        self.connector_index = 0
        self.current_ride = self.connectors[self.connector_index]
        self.carousel_enabled = False
        self.chunk_size = config["CHUNK_SIZE_KB"]
        self.chunk_size_bytes = self.chunk_size * 1024
        self.currently_playing = ""
        self.current_filepath = ""
        self.interrupt = False
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
        self.current_filepath = os.path.join(config["FALLBACK_TRACK_DIR"], fallback_tracks[self.fallback_index])
        self.serve_file()
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
        if self.carousel_enabled:
            logger.info("Stopping carousel")
            self.interrupt = True
            self.carousel_enabled = False
        else:
            logger.warn("Tried to stop carousel when it is already stoppped")

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
        track_info =  MP3(self.current_filepath).info
        seconds_per_chunk = self.chunk_size_bytes / (track_info.bitrate / 8)
        sleep_time = (math.floor(seconds_per_chunk * 100) - 1) / 100.0
        logger.info(f"Starting to serve the next track...")
        logger.info(f"Track name: '{self.currently_playing}'")
        logger.info(f"Track bitrate: {int(track_info.bitrate/1000)}kbps")
        logger.info(f"Seconds per chunk (approx.): {seconds_per_chunk}; Chunk size: {self.chunk_size}kB")
        logger.info(f"Traffic per client (approx.): {int(self.chunk_size / seconds_per_chunk)}kBps")
        logger.info(f"Delay betweek chunk sends (approx.): {sleep_time}s")
        logger.info(f"Track duration: {track_info.length}s")
        return seconds_per_chunk, sleep_time, track_info.length

    def serve_file(self, track_name=None):
        if track_name is not None:
            self.currently_playing = track_name
        # Wait if some other thread is in here
        while True:
            if not self.free:
                sleep(1)
                logger.warning("Waiting until another thread frees the stream...")
            else:
                break

        self.interrupt = False
        self.free = False
        try:
            if self.currently_playing == "":
                self.set_track_name_from_metadata()

            seconds_per_chunk, sleep_time, length = self.get_track_info()

            with open(self.current_filepath, 'rb') as mp3file:
                # Get chunks for the initial burst
                burst_chunks = [mp3file.read(self.chunk_size_bytes) for _ in range(self.initial_burst_chunks)]
                while True:
                    if not self.interrupt:
                        if LoRadServer.connected_clients != 0:
                            # If we have burst_chunks var, this means that we're sending the initial burst of data
                            #  thus we just set current_data in the server and continue with out lives as normal
                            if burst_chunks:
                                track_end_time = datetime.datetime.now().timestamp() + length
                                LoRadServer.current_data = deque(burst_chunks)
                                burst_chunks = False
                                continue
                            
                            chunk = mp3file.read(self.chunk_size_bytes)
                            
                            # If the last chunk
                            if not chunk:
                                serve_end = datetime.datetime.now().timestamp()
                                LoRadServer.track_ended = True
                                break
                            else:
                                # Serving the chunk to LoRadServer which will send the chunk to the clients
                                LoRadServer.add_data(chunk)

                        # If we're sending a packet per .256 seconds , we'll wait for .24 seconds (check how sleep_time is created)
                        #  so that we're sending data faster to avoid buffering while also making users
                        #  have some pre-buffered future data. The problem of users having future data is mitigated below.
                        sleep(sleep_time)
                        self.currently_playing = ""
                        self.current_filepath = ""
                    else:
                        logger.info("Playback interrupted.")
                        break
            
            # We're sending data *too* fast sometimes
            #  The code below is to compensate for being such a fast boi
            #  We know the track duration and we know how long we've been transferring it
            #   so we sleep the difference after we're done with transferring the track
            if not self.interrupt:
                serve_delay = track_end_time - serve_end - (self.initial_burst_chunks * seconds_per_chunk)
                if serve_delay > 0:
                    logger.info(f"Serve delay is {serve_delay}.")
                    sleep(serve_delay)
        finally:
            self.free = True
            LoRadServer.track_ended = True

    def cleanup(self):
        if os.path.exists(self.current_filepath):
            os.remove(self.current_filepath)