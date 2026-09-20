from collections import Counter
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit

from lorad.audio.hub import get_hub
from lorad.common.utils.http_threads import NamedThreadingMixIn
from lorad.common.utils.logger import get_logger
from lorad.common.utils.misc import get_version, read_config

logger = get_logger()
config = read_config()


class ThreadingHTTPServer(NamedThreadingMixIn, HTTPServer):
    thread_prefix = "WRK#"


class AudioStream(BaseHTTPRequestHandler):
    connected_clients = 0
    MAX_CLIENTS = config["MAX_CLIENTS"] if "MAX_CLIENTS" in config else 10
    MAX_SINGLE_IP_CLIENTS = config["MAX_SINGLE_IP_CLIENTS"] if "MAX_SINGLE_IP_CLIENTS" in config else 2
    kick_list = []
    clients = []

    @staticmethod
    def log_message(*args):
        pass

    def __init__(self, request, client_address, server):
        self.client_address = client_address
        self.server_version = f"LoRaD Radio v.{get_version()}"
        self.sys_version = ""
        super().__init__(request, client_address, server)

    def _send_404(self):
        self.send_response(404)
        self.end_headers()
        self.wfile.write("<html><h1>404</h1></html>".encode("utf-8"))
        self.wfile.flush()

    def _is_stream_path(self):
        # cache busters are appended by the frontend, so ignore the query string
        return urlsplit(self.path).path == "/"

    def _send_no_cache_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")

    def do_HEAD(self):
        if not self._is_stream_path():
            self._send_404()
            return
        self.send_response(200)
        self.send_header("Content-type", "audio/mpeg")
        self._send_no_cache_headers()
        self.end_headers()

    def do_GET(self):
        if not self._is_stream_path():
            self._send_404()
            return
        ip_from_headers = self.headers.get("X-Real-IP")
        if ip_from_headers is not None:
            self.client_address = (ip_from_headers, self.client_address[1])

        while True:
            client_id = hashlib.sha256(
                (self.client_address[0] + str(self.client_address[1])).encode("utf-8")
            ).hexdigest()[:4]
            if client_id not in [c[0] for c in AudioStream.clients]:
                AudioStream.clients.append((client_id, self.client_address[0]))
                break
        AudioStream.connected_clients += 1
        logger.info(
            f"Client [{client_id} ({self.client_address[0]})] connected. Connected clients: {AudioStream.connected_clients}"
        )
        try:
            if self.client_address[0] in AudioStream.kick_list:
                self.gtfo()
                raise RuntimeError(f"[{self.client_address[0]}] is in kick list.")

            if AudioStream.connected_clients > AudioStream.MAX_CLIENTS:
                self.ddos_protection()
                raise RuntimeError("Asked to wait for a while")

            self.send_response(200)
            self.send_header("Connection", "Close")
            self.send_header("Content-type", "audio/mpeg")
            self._send_no_cache_headers()
            self.send_header("Client-ID", f"{client_id}")
            self.end_headers()

            hub = get_hub()
            last_seq = -1
            while True:
                if self.client_address[0] in AudioStream.kick_list:
                    raise RuntimeError(f"[{self.client_address[0]}] is in kick list.")
                seq, chunk = hub.wait_chunk(last_seq)
                if seq == last_seq or not chunk:
                    continue
                last_seq = seq
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            logger.info(
                f"Client [{client_id} ({self.client_address[0]})] disconnected. Connected clients: {AudioStream.connected_clients - 1}"
            )
        except RuntimeError as e:
            logger.info(
                f"Client [{client_id} ({self.client_address[0]})] was kicked: ({e}) Connected clients: {AudioStream.connected_clients - 1}"
            )
        except Exception as e:
            logger.info(
                f"Client [{client_id} ({self.client_address[0]})] disconnected with an error: ({e.__class__.__name__}) Connected clients: {AudioStream.connected_clients - 1}"
            )
            logger.exception(e)
        finally:
            self.remove_client(client_id)
            AudioStream.connected_clients -= 1

    def remove_client(self, client_id):
        for anum, anitem in enumerate(AudioStream.clients):
            if anitem[0] == client_id:
                del AudioStream.clients[anum]
                return
        logger.error(f"Was told to remove client [{client_id}] but the client does not exist!")

    def ddos_protection(self):
        logger.warn(f"Too many clients ({AudioStream.connected_clients}/{AudioStream.MAX_CLIENTS})! DDOS?")
        ip_list = [x[1] for x in AudioStream.clients]
        ip_frequency = dict(Counter(ip_list))
        for anitem in ip_frequency:
            if ip_frequency[anitem] > AudioStream.MAX_SINGLE_IP_CLIENTS:
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
        self.send_header("Location", "https://www.youtube.com/watch?v=mjuS_vZ2Gp4")
        self.end_headers()


def start(server):
    logger.info(f"Ready. Listening on port {config['LISTEN_PORT']}.")
    server.serve_forever()
