import os
import subprocess
import time
from collections import deque
from threading import Thread
from typing import Deque

from lorad.common.utils.globs import END_OF_TRANSCODED_DATA
from lorad.common.utils.logger import get_logger
from lorad.common.utils.misc import read_config


logger = get_logger()


class Transcoder:
    def __init__(self, input_format, output_format="mp3", respect_chunk_size=False):
        self.respect_chunk_size = respect_chunk_size
        self.config = read_config()
        self.data_in : Deque[bytes] = deque()
        self.bytes_per_chunk = self.config["CHUNK_SIZE_KB"] * 1024
        logger.debug(f"Transcoder chunk size: {self.bytes_per_chunk}b")
        self.transcoder_buffer = b''
        # This should be set to True when you have finished passing file data to the transcoder.
        self.no_more_data = False
        self.input_format = input_format
        self.output_format = output_format
        self.ffmpeg_process = None
        self.loop_thread = None
        self.interrupt = False
        self.burst_done = False
    
    def ffmpeg_alive(self):
        return self.ffmpeg_process and self.ffmpeg_process.poll() is None
    
    def start(self):
        logger.info(f"Starting transcoder: {self.input_format} -> {self.output_format}")
        logger.info(f"Output bitrate: {self.config["BITRATE_KBPS"]}")
        if self.respect_chunk_size:
            logger.info(f"Chunk size (respected): {self.bytes_per_chunk}")
        self.__start_ffmpeg()
        self.loop_thread = Thread(name="Transcoder", target=self.transcoder_loop)
        self.loop_thread.start()
        self.interrupt = False
    
    def stop(self):
        logger.info("Stopping transcoder")
        if self.ffmpeg_alive():
            self.__stop_ffmpeg()
            self.interrupt = True
            while True:
                if self.loop_thread.is_alive():
                    logger.info("Waiting for the transcoder thread to stop...")
                else:
                    logger.info("Transcoder thread is stopped.")
                    break
                time.sleep(0.5)
        else:
            logger.warn("Transcoder was already stopped")
    
    def transcoder_loop(self):
        logger.info("Entering transcoder loop")
        while True:
            if not self.interrupt:
                if len(self.data_in) > 0:
                    slab = b''
                    while True:
                        chunk = self.data_in.popleft()
                        if chunk and chunk is not None:
                            slab += chunk
                        if len(self.data_in) == 0:
                            self.__feed_ffmpeg(slab)
                            break
                else:
                    time.sleep(0.1)
                self.__get_transcoded_data()
            else:
                logger.info("Exiting transcoder loop.")
                break

    def __get_transcoded_data(self):
        chunk = self.ffmpeg_process.stdout.read()
        if chunk:
            #logger.debug(f"Got {len(chunk)}b from ffmpeg.")
            if self.transcoder_buffer is not None:
                self.transcoder_buffer += chunk

    # Returns data from self.transcoder_buffer one chunk at a call
    #  Returns whatever is left here if someone has said that no more data is present
    #  Returns b'EOTD' if there is no more data, and we've used the whole transcoder buffer
    def get_transcoded_chunk(self) -> bytes:


        # Create a burst chunk when the transcoder starts (this happens on start or on station/source switch)
        #  Without this, the user may experience buffering as they have a very small buffer.
        if not self.burst_done:
            if len(self.transcoder_buffer) >= self.bytes_per_chunk * 2:
                logger.info("Sending a burst chunk to AudioStream from a fresh transcoder instance.")
                tmpbuf = self.transcoder_buffer
                self.transcoder_buffer = b''
                self.burst_done = True
                return tmpbuf
            else:
                return b''

        if self.transcoder_buffer is None:
            return END_OF_TRANSCODED_DATA

        if self.respect_chunk_size:
            if len(self.transcoder_buffer) >= self.bytes_per_chunk:
                chunk = self.transcoder_buffer[:self.bytes_per_chunk]
                self.transcoder_buffer = self.transcoder_buffer[self.bytes_per_chunk:]
                return chunk
            if self.no_more_data and len(self.transcoder_buffer) < self.bytes_per_chunk:
                tmpbuf = self.transcoder_buffer
                self.transcoder_buffer = None
                return tmpbuf
        else:
            if self.no_more_data and not self.transcoder_buffer:
                self.transcoder_buffer = None
            else:
                tmpbuf = self.transcoder_buffer
                self.transcoder_buffer = b''
                return tmpbuf
        return b''

    def add_data(self, data: bytes):
        #logger.debug(f"Adding {len(data)}b of data to transcoder queue.")
        if not self.interrupt:
            if isinstance(data, bytes):
                self.data_in.append(data)
            else:
                logger.warning(f"Got wrongly-typed chunk: {type(data)}")

    def __feed_ffmpeg(self, chunk) -> bool:
        if not chunk or chunk is None:
            return
        #logger.debug(f"Feeding ffmpeg {len(chunk)}b of data.")
        if self.ffmpeg_alive():
            try:
                self.ffmpeg_process.stdin.write(chunk)
                return True
            except Exception as e:
                logger.error(f"Can't feed ffmpeg: {e}")
                logger.exception(e)
                self.ffmpeg_process.stdin.close()
                logger.info(self.ffmpeg_process.stderr.read().decode("utf-8"))
                return False
        else:
            logger.error("Can't feed ffmpeg: da process is ded")
            return False
    
    def __start_ffmpeg(self):
        command = [
            'ffmpeg',
            '-hide_banner',
            '-loglevel', 'error',
            '-f', self.input_format,
            '-i', 'pipe:0',
            '-c:a', self.output_format,
            '-b:a', f'{self.config["BITRATE_KBPS"]}k',
            '-ar', '44100',
            '-f', 'mp3',
            'pipe:1'
        ]
        logger.debug("Starting: " + " ".join(command))
        self.ffmpeg_process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0
        )
        os.set_blocking(self.ffmpeg_process.stdout.fileno(), False)
        os.set_blocking(self.ffmpeg_process.stderr.fileno(), False)
        os.set_blocking(self.ffmpeg_process.stdin.fileno(), False)
    
    def __stop_ffmpeg(self):
        logger.info("Stopping ffmpeg.")
        self.ffmpeg_process.stdin.close()
        self.ffmpeg_process.terminate()
