import requests
from lorad.api.LoRadAPISrv import read_config
from lorad.common.utils.logger import get_logger
from lorad.common.utils.misc import read_stations
from lorad.audio.server import LoRadSrv
from lorad.audio.playback.FileStreamer import sleep
from lorad.audio.server.LoRadSrv import LoRadServer
from lorad.audio.playback.utils import FFMPEGFeedError
from lorad.audio.playback.utils.Transcoder import Transcoder

logger = get_logger()
config = read_config()

class RadioReStreamer:
    def __init__(self, server: LoRadSrv):
        self.server = server
        self.enabled = False
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
            if self.enabled:
                self.__prepare_and_start(self.current_station)
            else:
                sleep(0.5)
    
    def start(self):
        self.enabled = True
    
    # Stop everything, wait for the transmission to finish
    def stop(self):
        if self.transcoder is not None:
            self.transcoder.stop()
        self.enabled = False
        while True:
            if not self.transmitting:
                return
            sleep(0.2)
    
    def __prepare_and_start(self, station):
        stations = self.get_stations()
        station_url = ""
        if station in stations:
            station_url = stations[station]
        if station_url == "":
            logger.error(f"Station not found: {station}")
            return
        else:
            if self.preflight_request(station_url):
                if self.station_info["format"] != self.default_format:
                    bitrate = self.station_info["bitrate"] if "bitrate" in self.station_info else 320
                    self.transcoder = Transcoder(bitrate, self.station_info["format"], self.default_format)
                logger.info(f"Starting streaming '{station}'. Stream settings:")
                logger.info(f"URL: {station_url}")
                for akey, aval in self.station_info.items():
                    logger.info(f"{akey.capitalize()}: {aval}")
                logger.info(f"Transcoder enabled: {self.transcoder is not None}")
                if self.transcoder is not None:
                    self.transcoder.start()
                    self.__stream_transcoded(station_url)
                else:
                    self.__stream_untranscoded(station_url)

                # If we are outside of __stream_data and were not interrupted, we crashed
                if self.enabled:
                    logger.error("ReStreamer crashed. See previous errors.")
    
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
    
    def __stream_untranscoded(self, station_url):
        ext_strm_data_generator = self.consume_external_stream(station_url)
        try:
            self.transmitting = True
            for raw_chunk in ext_strm_data_generator:
                if self.enabled:
                    chunk = raw_chunk
                    if chunk:
                        LoRadServer.add_data(chunk)
                else:
                    ext_strm_data_generator.close()
                    break
            self.transmitting = False
        except GeneratorExit:
            logger.info("Playback interrupted.")
    
    def __stream_transcoded(self, station_url):
        ext_strm_data_generator = self.consume_external_stream(station_url)
        transcoded_chunk = b''
        try:
            self.transmitting = True
            for raw_chunk in ext_strm_data_generator:
                if self.enabled:
                    self.transcoder.add_data(raw_chunk)
                    transcoded_chunk = self.transcoder.get_transcoded_slab()
                    if transcoded_chunk and transcoded_chunk is not None:
                        LoRadServer.add_data(transcoded_chunk)
                else:
                    ext_strm_data_generator.close()
                    break
            self.transmitting = False
        except GeneratorExit:
            logger.info("Playback interrupted.")
        except FFMPEGFeedError:
            logger.error("Could not feed ffmpeg.")
    
    def consume_external_stream(self, stream_url):
        while True:
            for adata in requests.get(stream_url, stream=True):
                #logger.debug(f"Yielded {len(adata)} BOD from the remote stream")
                yield adata