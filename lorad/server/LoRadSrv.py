from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from socketserver import ThreadingMixIn
from threading import Thread
import threading
from time import sleep

from lorad.utils.logger import get_logger

logger = get_logger()

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    pass

class LoRadServer(BaseHTTPRequestHandler):
    connected_clients = 0
    thread_count = 1
    current_data = bytes()

    def __init__(self, request, client_address, server):
        super().__init__(request, client_address, server)

    def log_message(*args):
        pass

    def do_GET(self):
        if LoRadServer.connected_clients > 10:
            logger.error("Too many clients! DDOS?")
            os._exit(1)
        threading.current_thread().name = f"WRK#{LoRadServer.thread_count}"
        LoRadServer.connected_clients += 1
        pushed_data = bytes()
        logger.info(f"A client connected. Connected clients: {LoRadServer.connected_clients}")
        try:
            self.send_response(200)
            self.send_header("Connection", "Close")
            self.send_header("Content-type", "audio/mpeg")
            self.send_header("Cache-Control", "no-cache, no-store")
            self.end_headers()
            while True:
                if LoRadServer.current_data != pushed_data:
                    #logger.debug(f"Sending chunk to {self.client_address}: {len(LoRadServer.current_data)}b")
                    self.wfile.write(LoRadServer.current_data)
                    self.wfile.flush()
                    pushed_data = LoRadServer.current_data
                sleep(0.1)
        except (BrokenPipeError, ConnectionResetError) as e:
            logger.info(f"A client disconnected. Connected clients: {LoRadServer.connected_clients-1}")
        except Exception as e:
            logger.info(f"A client disconnected: ({e.__class__.__name__}) Connected clients: {LoRadServer.connected_clients-1}")
            logger.exception(e)
        LoRadServer.connected_clients -= 1