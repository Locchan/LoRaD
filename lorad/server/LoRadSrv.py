from collections import deque
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import random
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

    # This gets some chunks at the start
    #  by default users get only the first chunk
    #  But when a user first connects is gets a burst of data (this whole array)
    current_data = deque()

    # If track_ended is passed from the streamer, we should send all data that is left in current_data
    #  before it gets completely rewritten by the new track
    track_ended = False

    client_names = []

    def add_data(data):
        LoRadServer.current_data.popleft()
        LoRadServer.current_data.append(data)

    def __init__(self, request, client_address, server):
        super().__init__(request, client_address, server)

    def log_message(*args):
        pass

    def do_GET(self):
        while True:
            client_id = hashlib.sha256((self.client_address[0] + str(self.client_address[1])).encode("utf-8")).hexdigest()[:4]
            if client_id not in LoRadServer.client_names:
                LoRadServer.client_names.append(client_id)
                break
        LoRadServer.thread_count += 1
        if LoRadServer.connected_clients > 10:
            logger.error("Too many clients! DDOS?")
            os._exit(1)
        threading.current_thread().name = f"WRK#{LoRadServer.thread_count}"
        LoRadServer.connected_clients += 1
        pushed_data = bytes()
        logger.info(f"Client [{client_id}] connected. Connected clients: {LoRadServer.connected_clients}")
        try:
            self.send_response(200)
            self.send_header("Connection", "Close")
            self.send_header("Content-type", "audio/mpeg")
            self.send_header("Cache-Control", "no-cache, no-store")
            self.send_header("Client-ID", f"{client_id}")
            self.end_headers()
            last_burst_chunk = bytes()

            # Main loop. Each iteration is a new track
            while True:
                send_regularly = False

                # Sending initial burst of data for the newly-connected clients (or track starts) and setting last_burst_chunk
                # When the client reaches last_burst_chunk, this means that we can
                #  proceed as normal.
                #  current_data is being copied to be thread-safe
                while True:
                    current_data = deque(LoRadServer.current_data)
                    if len(current_data) > 0:
                        data_to_push = bytes()
                        for data_to_push in current_data:
                            logger.debug(f"[{client_id}] Sending a burst chunk [{hashlib.sha256(data_to_push).hexdigest()[:8]}]; Length: {len(data_to_push)}")
                            self.wfile.write(data_to_push)
                            self.wfile.flush()
                        last_burst_chunk = data_to_push
                        break
                    sleep(0.1)

                while True:

                    # If we get a new track, we should burst data. We burst data by breaking from this [while True:]
                    #  We detect a new track by detecting that our current_data has completely changed
                    #  (for every new track our streamer sends us a fresh batch of data, not just a single chunk)
                    if self.track_ended:
                        if self.detect_new_track(current_data, LoRadServer.current_data):
                            logger.debug(f"[{client_id}] New track detected.")
                            LoRadServer.track_ended = False
                            break
                    
                    #  Current_data is being copied to be thread-safe
                    current_data = deque(LoRadServer.current_data)

                    # current_data[0] can be false if we reached the end of the track
                    if len(current_data) > 0 and current_data[0]:
                        data_to_push = current_data[0]
                        if send_regularly and data_to_push != pushed_data:
                            logger.debug(f"[{client_id}] Sending a chunk [{hashlib.sha256(data_to_push).hexdigest()[:8]}]; Length: {len(data_to_push)}")
                            self.wfile.write(data_to_push)
                            self.wfile.flush()
                            if LoRadServer.track_ended:
                                LoRadServer.add_data(False)
                        elif data_to_push != pushed_data and not send_regularly:
                            logger.debug(f"[{client_id}] Skipping a chunk [{hashlib.sha256(data_to_push).hexdigest()[:8]}]: not yet at the burst end")
                            if data_to_push == last_burst_chunk:
                                pushed_data = last_burst_chunk
                                send_regularly = True
                        # Pushing falses to the current_data array until we squeezed out all the data and are left with an array of falses
                        #  This just starts the cycle, it will continue above
                        elif data_to_push == pushed_data and LoRadServer.track_ended:
                            if current_data[0] != False:
                                logger.debug("The track ended. Squeezing leftovers from our streamer.")
                                LoRadServer.add_data(False)
                        pushed_data = data_to_push
                    sleep(0.1)
        except (BrokenPipeError, ConnectionResetError) as e:
            logger.info(f"A client disconnected. Connected clients: {LoRadServer.connected_clients-1}")
        except Exception as e:
            logger.info(f"A client disconnected: ({e.__class__.__name__}) Connected clients: {LoRadServer.connected_clients-1}")
            logger.exception(e)
        finally:
            LoRadServer.client_names.remove(client_id)
            LoRadServer.thread_count -= 1
            LoRadServer.connected_clients -= 1
        
    def detect_new_track(self, current_data, old_data):
        return not set(current_data) & set(old_data)