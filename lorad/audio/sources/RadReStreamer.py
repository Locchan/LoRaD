import os

import requests
from lorad.api.LoRadAPISrv import read_config
from lorad.common.localization.localization import get_loc
from lorad.common.utils.logger import get_logger
from lorad.common.utils.misc import read_stations
from lorad.audio.server import AudioStream
from lorad.audio.sources.FileStreamer import sleep
from lorad.audio.server.AudioStream import AudioStream
from lorad.audio.sources.utils import FFMPEGFeedError
from lorad.audio.sources.utils.Transcoder import Transcoder

logger = get_logger()
config = read_config()

class RadReStreamer:
    def __init__(self, server: AudioStream):
        self.name_readable = get_loc("PLAYER_NAME_RADRESTREAMER")
        self.name_tech = "player_radio"
        self.server = server
        self.running = False
        self.transmitting = False
        self.stations = {}
        self.station_info = {}
        self.default_format = config["DEFAULT_AUDIO_FORMAT"]
        self.transcoder = None
        self.current_station = "default"
        self.get_stations()

    def get_stations(self) -> dict:
        self.stations = read_stations()
        return self.stations
    
    def standby(self):
        while True:
            if self.running:
                # Non-None return from this means that we detected an unrecoverable error, thus we break.
                result = self.__prepare_and_start(self.current_station)
                if result is not None:
                    if not result:
                        logger.error("Could not start stream. Check logs.")
                        return
                    else:
                        logger.info("Exited from radio loop")
                else:
                    logger.error("Exited from radio loop. Crashed?")
            else:
                sleep(0.5)
    
    def start(self):
        self.running = True
    
    # Stop everything, wait for the transmission to finish
    def stop(self):
        if self.transcoder is not None:
            self.transcoder.stop()
        self.running = False
        while True:
            if not self.transmitting:
                return
            sleep(0.2)
    
    def __prepare_and_start(self, station):
        stations = self.get_stations()
        station_url = ""
        if station in stations:
            station_url = stations[station]["url"]
        if station_url == "":
            logger.error(f"Station not found: {station}")
            return False
        else:
            self.currently_playing = stations[station]["name"]
            self.currently_playing = stations[station]["name"]
            if self.preflight_request(station_url):
                self.transcoder = Transcoder(self.station_info["format"], self.default_format)
                logger.info(f"Starting streaming '{station}'. Stream settings:")
                logger.info(f"URL: {station_url}")
                for akey, aval in self.station_info.items():
                    logger.info(f"{akey.capitalize()}: {aval}")
                logger.info(f"Transcoder running: {self.transcoder is not None}")
                if self.transcoder is not None:
                    self.transcoder.start()
                    self.__stream(station_url)
                else:
                    logger.error("Transcoder failed to start!")
                    os._exit(1)

                # If we are outside __stream_data and were not interrupted, we crashed
                if self.running:
                    logger.error("ReStreamer crashed. See previous errors.")
                    return False
                else:
                    return True
    
    # This checks the radio and gets some info like the audio format, bitrate, etc.
    def preflight_request(self, station_url):
        headers = {}
        with requests.get(station_url, stream=True) as response:
            status_code = response.status_code
            if status_code == 200:
                for header, value in response.headers.items():
                    headers[header] = value
                response.close()
        self.station_info = {}
        if 'ice-audio-info' in headers:
            audio_info_dict = dict(item.split('=') for item in headers['ice-audio-info'].split(';'))
            self.station_info["bitrate"] = audio_info_dict["ice-bitrate"]
        if 'Content-Type' in headers:
            self.station_info["format"] = headers['Content-Type'].split("/")[-1]
        return True
    
    def __stream(self, station_url):
        ext_strm_data_generator = self.consume_external_stream(station_url)
        transcoded_chunk = b''
        try:
            self.transmitting = True
            for raw_chunk in ext_strm_data_generator:
                if self.running:
                    self.transcoder.add_data(raw_chunk)
                    transcoded_chunk = self.transcoder.get_transcoded_chunk()
                    if transcoded_chunk and transcoded_chunk is not None:
                        AudioStream.add_data(transcoded_chunk)
                else:
                    ext_strm_data_generator.close()
                    break
            self.transmitting = False
        except GeneratorExit:
            logger.info("Playback interrupted.")
        except FFMPEGFeedError:
            logger.error("Could not feed ffmpeg.")
    
    def consume_external_stream(self, stream_url):
        error_iterations = 0
        while True:
            try:
                for adata in requests.get(stream_url, stream=True):
                    #logger.debug(f"Yielded {len(adata)} BOD from the remote stream")
                    error_iterations = 0
                    yield adata
            # Retry right away on the first error. If still erroring out, then sleep error_iterations * 2 but no more than 15 seconds.
            except Exception as e:
                error_iterations += 1
                if error_iterations > 1:
                    retry_time = error_iterations * 2
                    if retry_time > 15:
                        retry_time = 15
                        logger.warning(f"Error while reading {stream_url}: {e.__class__.__name__}. Retrying in {retry_time}s.")
                        sleep(retry_time)