import datetime
import os
from time import sleep
from lorad.connectors.Connector import Connector
from lorad.server.LoRadSrv import LoRadServer
from lorad.utils.logger import get_logger
from mutagen.mp3 import MP3

logger = get_logger()

class Carousel():
    chunk_size = 10240

    def __init__(self, connectors: list[Connector], server: LoRadServer):
        logger.debug("Initializing carousel...")
        self.server = server
        self.connectors = connectors
        self.connector_index = 0
        self.current_connector = self.connectors[self.connector_index]
        self.carousel_enabled = False

    def carousel(self):
        logger.debug("Entering carousel")
        while True:
            if self.carousel_enabled:
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
            self.carousel_enabled = False
        else:
            logger.warn("Tried to stop carousel when it is already stoppped")

    def serve_file(self, filepath):
        #                            bytes                        kbits -> bytes
        seconds_per_packet = Carousel.chunk_size / ((self.current_connector.bitrate * 1024) / 8)
        logger.info(f"Serving [{filepath}]...")
        logger.info(f"Seconds per chunk: {seconds_per_packet}; Chunk size {Carousel.chunk_size}b")
        serve_start = datetime.datetime.now().timestamp()
        track_len = MP3(filepath).info.length
        logger.info(f"Track length: {track_len}s")
        with open(filepath, 'rb') as mp3file:
            while True:
                if self.carousel_enabled:
                    if LoRadServer.connected_clients != 0:
                        #logger.debug(f"Reading {Carousel.chunk_size}b from {filepath}...")
                        chunk = mp3file.read(Carousel.chunk_size)
                        # The last chunk will be empty or less than chunk_size
                        if not chunk or len(chunk) < Carousel.chunk_size:
                            break
                        else:
                            LoRadServer.current_data = bytes(chunk)
                    sleep(seconds_per_packet)
                else:
                    break
        
        # We're sending data too fast to avoid buffering on unstable networks
        #  This is to compensate for being such a fast boi
        #  We know the track duration and we know how long we've been transferring it
        #   so we sleep the difference after we're done with transferring the track
        serve_end = datetime.datetime.now().timestamp()
        serve_delay = serve_end - (serve_start + track_len)
        logger.info(f"Serve delay is {serve_delay}.")
        sleep(serve_delay if serve_delay > 0 else 0)

    def cleanup(self, filename):
        if os.path.exists(filename):
            os.remove(filename)