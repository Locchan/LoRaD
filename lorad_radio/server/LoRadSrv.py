from collections import Counter, deque
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import threading
from time import sleep

from lorad_radio.utils.logger import get_logger
from lorad_radio.utils.utils import read_config

logger = get_logger()
config = read_config()

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    pass


class LoRadServer(BaseHTTPRequestHandler):
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

    clients = []

    @staticmethod
    def add_data(data):
        LoRadServer.current_data.popleft()
        LoRadServer.current_data.append(data)

    @staticmethod
    def log_message(*args):
        pass

    def __init__(self, request, client_address, server):
        super().__init__(request, client_address, server)

    def do_GET(self):
        # If X-Real-IP exists, then we're proxied.
        # When we're proxied, self.client address will have our proxy IP inside, not the clients IP
        ip_from_headers = self.headers.get('X-Real-IP')
        if ip_from_headers is not None:
            self.client_address = (ip_from_headers, self.client_address[1])

        type_err = bytes

        while True:
            client_id = hashlib.sha256((self.client_address[0] + str(self.client_address[1]))
                                       .encode("utf-8")).hexdigest()[:4]
            if client_id not in LoRadServer.clients:
                LoRadServer.clients.append((client_id, self.client_address[0]))
                break
        LoRadServer.thread_count += 1
        threading.current_thread().name = f"WRK#{LoRadServer.thread_count}"
        LoRadServer.connected_clients += 1
        pushed_data = bytes()
        logger.info(f"Client [{client_id} ({self.client_address[0]})] connected. Connected clients: {LoRadServer.connected_clients}")
        try:

            # If we're in kick list, we get kicked (nuff said)
            if self.client_address[0] in LoRadServer.kick_list:
                self.gtfo()
                raise RuntimeError(f"[{self.client_address[0]}] is in kick list.")

            if LoRadServer.connected_clients > LoRadServer.MAX_CLIENTS:
                self.ddos_protection()
                raise RuntimeError("Asked to wait a while")

            self.send_response(200)
            self.send_header("Connection", "Close")
            self.send_header("Content-type", "audio/mpeg")
            self.send_header("Cache-Control", "no-cache, no-store")
            self.send_header("Client-ID", f"{client_id}")
            self.end_headers()

            # Main loop. Each iteration is a new track
            while True:

                # Stop sending data to a kicked client.
                if self.client_address[0] in LoRadServer.kick_list:
                    raise RuntimeError(f"[{self.client_address[0]}] is in kick list.")

                # Sending initial burst of data for the newly-connected clients (or when the track starts)
                #  current_data is being copied to be thread-safe
                while True:
                    current_data = deque(LoRadServer.current_data)
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
                        if self.detect_new_track(current_data, LoRadServer.current_data):
                            logger.debug(f"[{client_id}] New track detected.")
                            LoRadServer.track_ended = False
                            break
                    
                    #  Current_data is being copied to be thread-safe
                    current_data = deque(LoRadServer.current_data)

                    if len(current_data) > 0:
                        data_to_push = current_data[-1]
                        if data_to_push != pushed_data:
                            if isinstance(data_to_push, bytes) and not isinstance(data_to_push, type_err):
                                type_err = type(data_to_push)
                                logger.error(f"Wrong data type! Got [{type_err}] as data to push!")
                                continue
                            type_err = bytes
                            # logger.debug(f"[{client_id}] Sending a chunk [{hashlib.sha256(data_to_push).hexdigest()[:8]}]; Length: {len(data_to_push)}")
                            self.wfile.write(data_to_push)
                            self.wfile.flush()
                            if LoRadServer.track_ended:
                                LoRadServer.add_data(False)
                        pushed_data = data_to_push
                    sleep(0.1)
        except (BrokenPipeError, ConnectionResetError):
            logger.info(f"Client [{client_id} ({self.client_address[0]})] disconnected. Connected clients: {LoRadServer.connected_clients-1}")
        except RuntimeError as e:
            logger.info(f"Client [{client_id} ({self.client_address[0]})] was kicked: ({e}) Connected clients: {LoRadServer.connected_clients-1}")
        except Exception as e:
            logger.info(f"Client [{client_id} ({self.client_address[0]})] disconnected with an error: ({e.__class__.__name__}) Connected clients: {LoRadServer.connected_clients-1}")
            logger.exception(e)
        finally:
            self.remove_client(client_id)
            LoRadServer.thread_count -= 1
            LoRadServer.connected_clients -= 1
        
    def detect_new_track(self, current_data, old_data):
        return not set(current_data) & set(old_data)

    def remove_client(self, client_id):
        num_to_delete = -1
        for anum, anitem in enumerate(LoRadServer.clients):
            if anitem[0] == client_id:
                num_to_delete = anum
        if num_to_delete >= 0:
            del LoRadServer.clients[num_to_delete]
        else:
            logger.error(f"Was told to remove client [{client_id}] but the client does not exist!")

    # Considering every IP with >2 connections a DUDOSERs
    def ddos_protection(self):
        logger.warn(f"Too many clients ({LoRadServer.connected_clients}/{LoRadServer.MAX_CLIENTS})! DDOS?")
        logger.info("Searching for dudoseri...")
        ip_list = [x[1] for x in LoRadServer.clients]
        ip_frequency = dict(Counter(ip_list))
        for anitem in ip_frequency:
            if ip_frequency[anitem] > 2:
                logger.info(f"Dudoser: {anitem}")
                LoRadServer.kick_list.append(anitem)
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