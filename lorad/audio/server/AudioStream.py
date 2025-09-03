import datetime
from collections import Counter, deque
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import threading
from time import sleep

from lorad.common.utils.logger import get_logger
from lorad.common.utils.misc import get_version, read_config

logger = get_logger()
config = read_config()

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    pass


class AudioStream(BaseHTTPRequestHandler):
    connected_clients = 0
    MAX_CLIENTS = config["MAX_CLIENTS"] if "MAX_CLIENTS" in config else 10
    thread_count = 1

    # List of IP addresses to kick
    #  Users get into this list by trying to DDOS.
    kick_list = []

    # This gets some chunks at the start
    #  by default users get only the last chunk
    #  But when a user connects for the first time, they get a burst of data (this whole array)
    current_data = deque()

    # If track_ended is passed from the streamer, we should send all data that is left
    #  in current_data before it gets completely rewritten by the new track
    track_ended = False

    # This flag should be used to switch station. This makes all threads to stop sending current data and get new data
    player_switch = False

    clients = []

    @staticmethod
    def add_data(data, only_if_listeners_there=False):
        accept_data = True
        if only_if_listeners_there and AudioStream.connected_clients == 0:
            accept_data = False
        if accept_data:
            if len(AudioStream.current_data) > 0:
                AudioStream.current_data.popleft()
            AudioStream.current_data.append(data)
        return accept_data

    @staticmethod
    def log_message(*args):
        pass

    def __init__(self, request, client_address, server):
        self.client_address = client_address
        self.server_version = f"LoRaD Radio v.{get_version()}"
        self.player_switched = 0
        self.sys_version = ""
        super().__init__(request, client_address, server)

    def do_HEAD(self):
        if self.path != '/':
            self.send_response(404)
            self.end_headers()
            self.wfile.write("<html><h1>404</h1></html>".encode("utf-8"))
            self.wfile.flush()
            return
        self.send_response(200)
        self.end_headers()
    
    def do_GET(self):
        if self.path != '/':
            self.send_response(404)
            self.end_headers()
            self.wfile.write("<html><h1>404</h1></html>".encode("utf-8"))
            self.wfile.flush()
            return
        # If X-Real-IP exists, then we're proxied.
        # When we're proxied, self.client address will have our proxy IP inside, not the real client's IP
        ip_from_headers = self.headers.get('X-Real-IP')
        if ip_from_headers is not None:
            self.client_address = (ip_from_headers, self.client_address[1])

        type_err = bytes

        while True:
            client_id = hashlib.sha256((self.client_address[0] + str(self.client_address[1]))
                                       .encode("utf-8")).hexdigest()[:4]
            if client_id not in AudioStream.clients:
                AudioStream.clients.append((client_id, self.client_address[0]))
                break
        AudioStream.thread_count += 1
        threading.current_thread().name = f"WRK#{AudioStream.thread_count}"
        AudioStream.connected_clients += 1
        pushed_data = bytes()
        logger.info(f"Client [{client_id} ({self.client_address[0]})] connected. Connected clients: {AudioStream.connected_clients}")
        try:

            # If we're in kick list, we get kicked (nuff said)
            if self.client_address[0] in AudioStream.kick_list:
                self.gtfo()
                raise RuntimeError(f"[{self.client_address[0]}] is in kick list.")

            if AudioStream.connected_clients > AudioStream.MAX_CLIENTS:
                self.ddos_protection()
                raise RuntimeError("Asked to wait for a while")

            self.send_response(200)
            self.send_header("Connection", "Close")
            self.send_header("Content-type", "audio/mpeg")
            self.send_header("Cache-Control", "no-cache, no-store")
            self.send_header("Client-ID", f"{client_id}")
            self.end_headers()

            # Main loop. Each iteration is a new track (radio is just an infinite track in this regard)
            while True:

                # Stop sending data to a kicked client.
                if self.client_address[0] in AudioStream.kick_list:
                    raise RuntimeError(f"[{self.client_address[0]}] is in kick list.")

                # Sending initial burst of data for the newly-connected clients (or when the track starts)
                #  current_data is being copied to be thread-safe
                while True:
                    current_data = deque(AudioStream.current_data)
                    if len(current_data) > 0:
                        data_to_push = bytes()
                        for data_to_push in current_data:
                            if data_to_push:
                                #logger.debug(f"[{client_id}] Sending a burst chunk [{hashlib.sha256(data_to_push).hexdigest()[:8]}]; Length: {len(data_to_push)}")
                                self.wfile.write(data_to_push)
                                self.wfile.flush()
                                pushed_data = data_to_push
                        break
                    sleep(0.1)

                while True:
                    # If we get a new track, we should burst data. We burst data by breaking from this [while True:]
                    #  We detect a new track by detecting that our current_data has completely changed
                    #  (for every new track our streamer sends us a fresh batch of data, not just a single chunk)
                    if self.track_ended:
                        if self.detect_new_track(current_data, AudioStream.current_data):
                            logger.debug(f"[{client_id}] New track detected.")
                            AudioStream.track_ended = False
                            break
                    
                    #  Current_data is being copied to be thread-safe
                    current_data = deque(AudioStream.current_data)

                    if len(current_data) > 0:
                        data_to_push = current_data[-1]
                        if data_to_push != pushed_data:
                            if not isinstance(data_to_push, bytes):
                                continue
                            #logger.debug(f"[{client_id}] Sending a chunk [{hashlib.sha256(data_to_push).hexdigest()[:8]}]; Length: {len(data_to_push)}")
                            self.wfile.write(data_to_push)
                            self.wfile.flush()
                            if AudioStream.track_ended:
                                AudioStream.add_data(False)
                        pushed_data = data_to_push
                    sleep(0.1)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            logger.info(f"Client [{client_id} ({self.client_address[0]})] disconnected. Connected clients: {AudioStream.connected_clients - 1}")
        except RuntimeError as e:
            logger.info(f"Client [{client_id} ({self.client_address[0]})] was kicked: ({e}) Connected clients: {AudioStream.connected_clients - 1}")
        except Exception as e:
            logger.info(f"Client [{client_id} ({self.client_address[0]})] disconnected with an error: ({e.__class__.__name__}) Connected clients: {AudioStream.connected_clients - 1}")
            logger.exception(e)
        finally:
            self.remove_client(client_id)
            AudioStream.thread_count -= 1
            AudioStream.connected_clients -= 1
        
    def detect_new_track(self, current_data, old_data):
        return not set(current_data) & set(old_data)

    def remove_client(self, client_id):
        num_to_delete = -1
        for anum, anitem in enumerate(AudioStream.clients):
            if anitem[0] == client_id:
                num_to_delete = anum
        if num_to_delete >= 0:
            del AudioStream.clients[num_to_delete]
        else:
            logger.error(f"Was told to remove client [{client_id}] but the client does not exist!")

    # Considering every IP with >2 connections a DUDOSER
    def ddos_protection(self):
        logger.warn(f"Too many clients ({AudioStream.connected_clients}/{AudioStream.MAX_CLIENTS})! DDOS?")
        logger.info("Searching for dudoseri...")
        ip_list = [x[1] for x in AudioStream.clients]
        ip_frequency = dict(Counter(ip_list))
        for anitem in ip_frequency:
            if ip_frequency[anitem] > 2:
                logger.info(f"Dudoser: {anitem}")
                AudioStream.kick_list.append(anitem)
        self.ddosed()

    def ddosed(self):
        self.send_response(503)
        self.end_headers()
        self.wfile.write("Overloaded. Try later.\n".encode("utf-8"))
        self.wfile.flush()

    def gtfo(self):
        self.send_response(302)
        self.send_header('Location', "https://www.youtube.com/watch?v=mjuS_vZ2Gp4")
        self.end_headers()

def start(server):
    logger.info(f"Ready. Listening on port {config['LISTEN_PORT']}.")
    server.serve_forever()