import time

import requests

from lorad.audio.hub import get_hub
from lorad.audio.sources.GenericPlayer import GenericPlayer
from lorad.common.localization.localization import get_loc
from lorad.common.utils.logger import get_logger
from lorad.common.utils.misc import read_config, read_stations

logger = get_logger()
config = read_config()


def parse_stream_headers(headers):
    headers = {key.lower(): value for key, value in headers.items()}
    station_info = {}

    ice_audio_info = headers.get("ice-audio-info")
    if ice_audio_info:
        try:
            audio_info_dict = dict(item.split("=") for item in ice_audio_info.split(";"))
            if "ice-bitrate" in audio_info_dict:
                station_info["bitrate"] = audio_info_dict["ice-bitrate"]
            elif "bitrate" in audio_info_dict:
                station_info["bitrate"] = audio_info_dict["bitrate"]
        except Exception:
            pass
    if "bitrate" not in station_info and "icy-br" in headers:
        station_info["bitrate"] = headers["icy-br"]

    content_type = headers.get("content-type")
    if content_type:
        if ";" not in content_type:
            station_info["format"] = content_type.split("/")[-1]
        else:
            station_info["format"] = content_type.split(";", 1)[0].split("/")[-1].strip()

    return station_info


def _kbps(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).split(",")[0]
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else None


class RadReStreamer(GenericPlayer):
    def __init__(self, server=None):
        self.name_readable = get_loc("PLAYER_NAME_RADRESTREAMER")
        self.name_tech = "player_radio"
        self.running = False
        self.stations = {}
        self.station_info = {}
        self.default_format = config["DEFAULT_AUDIO_FORMAT"]
        self.current_station = "default"
        self.currently_playing = self.current_station
        # Bumped on every station switch so a stream loop still on the old URL gives up.
        self._epoch = 0
        self.get_stations()

    def get_stations(self) -> dict:
        self.stations = read_stations()
        return self.stations

    def standby(self):
        hub = get_hub()
        while True:
            if not self.running:
                time.sleep(0.5)
                continue
            stations = self.get_stations()
            if self.current_station not in stations:
                logger.error(f"Station not found: {self.current_station}")
                time.sleep(5)
                continue
            epoch = self._epoch
            station_url = stations[self.current_station]["url"]
            self.currently_playing = stations[self.current_station]["name"]
            fmt = self.preflight_format(station_url) or self.default_format
            hub.acquire(self)
            logger.info(f"Starting streaming '{self.current_station}' ({fmt}) {station_url}")
            self._stream(hub, station_url, fmt, epoch)

    def start(self):
        self.running = True

    def stop(self):
        self.running = False
        get_hub().release(self)

    def list_sources(self, cached=False):
        stations = self.get_stations()
        return {stations[anitem]["name"]: anitem for anitem in stations}

    def current_source(self):
        return self.current_station

    def switch_source(self, source_id):
        self._epoch += 1
        self.stop()
        self.current_station = source_id
        self.start()

    def preflight_format(self, station_url):
        try:
            with requests.get(station_url, stream=True, timeout=10) as response:
                if response.status_code != 200:
                    return None
                info = parse_stream_headers(response.headers)
                self.station_info = info
                return info.get("format")
        except Exception as e:
            logger.warn(f"Preflight failed: {e.__class__.__name__}")
            return None

    def _stream(self, hub, station_url, fmt, epoch):
        error_iterations = 0
        while self.running and self._epoch == epoch:
            try:
                with requests.get(station_url, stream=True, timeout=30) as resp:
                    resp.raise_for_status()
                    error_iterations = 0
                    # every (re)connection is a new elementary stream, never splice it onto the old one
                    info = parse_stream_headers(resp.headers)
                    self.station_info = info
                    live_fmt = info.get("format") or fmt
                    hub.begin_source(self, live_fmt, bitrate_kbps=_kbps(info.get("bitrate")))
                    for raw_chunk in resp.iter_content(chunk_size=8192):
                        if not self.running or self._epoch != epoch:
                            return
                        if raw_chunk and not hub.feed(self, raw_chunk):
                            if hub.owner() is not self:
                                # Someone else plays now; standby will reconnect when we are back.
                                logger.info("Hub is no longer ours, dropping the station stream")
                                return
                            logger.warning("The hub stopped accepting audio, reconnecting")
                            break
            except Exception as e:
                if not self.running or self._epoch != epoch:
                    return
                error_iterations += 1
                retry_time = min(error_iterations * 2, 15)
                logger.warning(f"Error while reading {station_url}: {e.__class__.__name__}. Retrying in {retry_time}s.")
                time.sleep(retry_time)
