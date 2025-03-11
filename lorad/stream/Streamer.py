from collections import deque
import datetime
import math
import os
from time import sleep
from lorad.music.Connector import Connector
from lorad.server.LoRadSrv import LoRadServer
from lorad.utils.logger import get_logger
from mutagen.mp3 import MP3

from lorad.utils.utils import read_config

logger = get_logger()

class Streamer():
    def __init__(self, connectors: list[Connector], server: LoRadServer):
        logger.debug("Initializing carousel...")
        config = read_config()
        self.server = server
        self.connectors = connectors
        self.connector_index = 0
        self.current_connector = self.connectors[self.connector_index]
        self.carousel_enabled = False
        self.chunk_size = config["CHUNK_SIZE_KB"]
        self.chunk_size_bytes = self.chunk_size * 1024
        self.interrupt = False
        self.free = True
        self.initial_burst_chunks = 8

    def carousel(self):
        logger.debug("Entering carousel")
        while True:
            if self.carousel_enabled:
                if not self.current_connector.initialized:
                    self.current_connector.initialize()
                filepath = self.current_connector.get_current_track_file()
                # Serve chunks and exit when the end of the file is reached
                self.serve_file(filepath)
                self.cleanup(filepath)
                self.current_connector.next_track() 
                # Rotating connectors if possible
                self.connector_index += 1
                if len(self.connectors) > self.connector_index:
                    self.current_connector = self.connectors[self.connector_index]
                else:
                    self.current_connector = self.connectors[0]
            else:
                sleep(1)

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

    def serve_file(self, filepath):
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
            track_info = MP3(filepath).info
            seconds_per_packet = self.chunk_size_bytes / (track_info.bitrate / 8)
            sleep_time = (math.floor(seconds_per_packet * 100) - 1) / 100.0
            logger.info(f"Strarting to serve the next track...")
            logger.info(f"Track bitrate: {int(track_info.bitrate/1000)}kbps")
            logger.info(f"Seconds per chunk (approx.): {seconds_per_packet}; Chunk size: {self.chunk_size}kB")
            logger.info(f"Traffic per client (approx.): {int(self.chunk_size / seconds_per_packet)}kBps")
            logger.info(f"Delay betweek chunk sends (approx.): {sleep_time}s")
            logger.info(f"Track duration: {track_info.length}s")
            with open(filepath, 'rb') as mp3file:
                # Get chunks for the initial burst
                chunks = [mp3file.read(self.chunk_size_bytes) for _ in range(self.initial_burst_chunks)]
                while True:
                    if not self.interrupt:
                        if LoRadServer.connected_clients != 0:
                            # If we have chunks var, this means that we're sending the initial burst of data
                            #  thus we just set current_data in the server and continue with out lives as normal
                            if chunks:
                                track_end_time = datetime.datetime.now().timestamp() + track_info.length
                                LoRadServer.current_data = deque(chunks)
                                chunks = False
                                continue
                            
                            chunk = mp3file.read(self.chunk_size_bytes)
                            
                            # If the last chunk
                            if not chunk:
                                serve_end = datetime.datetime.now().timestamp()
                                LoRadServer.track_ended = True
                                break
                            else:
                                # Serving the chunk to LoRadServer which will sending the chunk to the clients
                                LoRadServer.add_data(chunk)

                        # If we're sending a packet per .256 seconds , we'll wait for .24 seconds (check how sleep_time is created)
                        #  so that we're sending data faster to avoid buffering but we also make users
                        #  have some pre-buffered future data. This is mitigated below.
                        sleep(sleep_time)
                    else:
                        logger.info("Playback interrupted.")
                        break
            
            # We're sending data *too* fast sometimes
            #  The code below is to compensate for being such a fast boi
            #  We know the track duration and we know how long we've been transferring it
            #   so we sleep the difference after we're done with transferring the track
            if not self.interrupt:
                serve_delay = math.ceil(track_end_time - serve_end)
                if serve_delay > 0:
                    logger.info(f"Serve delay is {serve_delay}.")
                    sleep(serve_delay)
        finally:
            self.free = True
            LoRadServer.track_ended = True

    def cleanup(self, filename):
        if os.path.exists(filename):
            os.remove(filename)