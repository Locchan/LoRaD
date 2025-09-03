#!/usr/bin/env python3

from http.server import ThreadingHTTPServer
from threading import Thread
from lorad.common.utils.logger import setdebug
from lorad.audio.server import AudioStream
from lorad.audio.server.AudioStream import AudioStream
from lorad.audio.sources.RadReStreamer import RadReStreamer
from lorad.common.utils.misc import get_version, read_config


setdebug()

config = read_config()

server = ThreadingHTTPServer(("0.0.0.0", config["LISTEN_PORT"]), AudioStream)
AudioStreamthread = Thread(name="HTTPServer", target=AudioStream.start, args=(server,))

AudioStreamthread.start()

restreamer = RadReStreamer(None)
restreamer.start("belarus")