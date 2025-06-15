import os
import subprocess
from threading import Thread
from typing import Deque
from lorad.common.utils.logger import get_logger
from lorad.audio.server.LoRadSrv import sleep
from lorad.audio.playback.FileStreamer import deque
from lorad.common.utils.misc import read_config


logger = get_logger()
config = read_config()


class Transcoder():
    def __init__(self, output_bitrate, input_format, output_format="mp3"):
        self.data_in : Deque[bytes] = deque()
        self.data_out : Deque[bytes] = deque()
        self.output_bitrate = int(output_bitrate)
        self.bytes_per_chunk = config["CHUNK_SIZE_KB"] * 1024
        logger.debug(f"Transcoder bytes per chunk {self.bytes_per_chunk}")
        self.input_format = input_format
        self.output_format = output_format
        self.ffmpeg_process = None
        self.loop_thread = None
        self.interrupt = False
    
    def ffmpeg_alive(self):
        return self.ffmpeg_process and self.ffmpeg_process.poll() is None
    
    def start(self):
        logger.info(f"Starting transcoder: {self.input_format} -> {self.output_format}")
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
                sleep(0.5)
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
                    sleep(0.1)
                self.__get_transcoded_data()
            else:
                logger.info("Exiting transcoder loop.")
                break

    def __get_transcoded_data(self):
        chunk = self.ffmpeg_process.stdout.read()
        if chunk:
            #logger.debug(f"Got {len(chunk)}b from ffmpeg.")
            self.data_out.append(chunk)

    def get_transcoded_slab(self):
        slab = b''
        if len(self.data_out) > 0:
            while True:
                chunk = self.data_out.popleft()
                if chunk and chunk is not None:
                    slab += chunk
                if len(self.data_out) == 0:
                    return slab

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
            '-b:a', f'{self.output_bitrate}k',
            '-f', 'mp3',
            'pipe:1'
        ]
        logger.info("Starting ffmpeg: ")
        logger.info(" ".join(command))
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
