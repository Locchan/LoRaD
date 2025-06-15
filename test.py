#!/usr/bin/env python3

from http.server import ThreadingHTTPServer
from threading import Thread
from lorad.common.utils.logger import setdebug
from lorad.audio.server import LoRadSrv
from lorad.audio.server.LoRadSrv import LoRadServer
from lorad.audio.playback.RadReStreamer import RadReStreamer
from lorad.common.utils.misc import get_version, read_config


setdebug()

config = read_config()

server = ThreadingHTTPServer(("0.0.0.0", config["LISTEN_PORT"]), LoRadServer)
loradsrvthread = Thread(name="HTTPServer", target=LoRadSrv.start, args=(server,))

loradsrvthread.start()

restreamer = RadReStreamer(None)
restreamer.start("belarus")