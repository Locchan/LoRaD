from urllib.parse import parse_qs, urlsplit
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
import json
import os

from lorad.api.utils.websocket import WebSocket, is_websocket_upgrade
from lorad.common.utils.http_threads import NamedThreadingMixIn
from lorad.common.utils.logger import get_logger
from lorad.common.utils.misc import get_version, read_config

endpoints = {}
ws_endpoints = {}
logger = get_logger()
config = read_config()
MAX_DATA_LEN = config["REST"]["MAX_DATA_LEN_BYTES"]
DEBUG_ONLY_PRINT_ENDPOINTS = ["/whatsplaying"]


def rest_listen_port():
    return config["REST"]["LISTEN_PORT"]


def ws_listen_port():
    return config["REST"].get("WS_LISTEN_PORT", 5478)


def register_endpoints():
    global endpoints, ws_endpoints
    logger.info("Registering API endpoints")
    import lorad.api.endpoints
    registered_endpoints = 0
    for endpoint_module in lorad.api.endpoints.endpoints_to_register:
        try:
            # To add support for other methods, specify them here and just implement impl_X methods in endpoint modules
            for amethod in ["GET", "POST"]:
                if amethod not in endpoints:
                    endpoints[amethod] = {}
                if amethod not in ws_endpoints:
                    ws_endpoints[amethod] = {}

                # If the endpoint module does not have impl_{amethod}, continue to look for other methods
                try:
                    impl = getattr(endpoint_module, f"impl_{amethod}")
                except AttributeError:
                    continue

                dest = ws_endpoints if getattr(impl, "_lrd_websocket", False) else endpoints
                kind = "WS" if dest is ws_endpoints else amethod
                logger.debug(f"Registering: {kind} - {endpoint_module.ENDP_PATH}")

                if endpoint_module.ENDP_PATH not in dest[amethod]:
                    dest[amethod][endpoint_module.ENDP_PATH] = impl
                    registered_endpoints += 1
                else:
                    logger.error(f"Could not register {amethod} endpoint from module {endpoint_module.__name__}: endpoint path already taken.")
                    os._exit(0)
        except Exception as e:
            logger.error(f"Could not register an endpoint: {endpoint_module.__name__}")
            logger.exception(e)
            os._exit(0)
    logger.info(f"Registered {registered_endpoints} endpoints.")


class ThreadingWSServer(NamedThreadingMixIn, HTTPServer):
    daemon_threads = True
    thread_prefix = "WS#"


class LoRadAPIServer(BaseHTTPRequestHandler):
    @staticmethod
    def log_message(*args):
        pass

    def __init__(self, request, client_address, server):
        self.server_version = f"LoRaD API v.{get_version()}"
        self.sys_version = ""
        super().__init__(request, client_address, server)

    def error(self, code, message):
        self.send_response(code)
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode("utf-8"))
        self.wfile.flush()

    def _send_cors_headers(self):
        origin = self.headers.get("Origin") or "*"
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Requested-With")
        self.send_header("Access-Control-Max-Age", "1728000")
        if origin != "*":
            self.send_header("Vary", "Origin")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def _write_endpoint_result(self, path, endpoint_exec_result):
        self.send_response(endpoint_exec_result["rc"])
        content_type = endpoint_exec_result.get("content-type", "application/json")
        self.send_header("Content-type", content_type)
        if endpoint_exec_result.get("cache-control"):
            self.send_header("Cache-Control", endpoint_exec_result["cache-control"])
        extra_headers = endpoint_exec_result.get("headers") or {}
        for header, value in extra_headers.items():
            self.send_header(header, value)
        if extra_headers:
            # The UI is served from another origin, so custom headers stay invisible to it otherwise
            self.send_header("Access-Control-Expose-Headers", ", ".join(extra_headers))
        self._send_cors_headers()
        self.end_headers()
        data = endpoint_exec_result["data"]
        binary = isinstance(data, (bytes, bytearray))
        if binary:
            body = bytes(data)
        elif isinstance(data, dict):
            body = json.dumps(data).encode("utf-8")
        else:
            body = str(data).encode("utf-8")
        self.wfile.write(body)
        self.wfile.flush()
        real_ip = self.headers.get("X-Real-IP") or self.client_address[0]
        size = len(body)
        log = logger.debug if path in DEBUG_ONLY_PRINT_ENDPOINTS and int(endpoint_exec_result["rc"]) == 200 else logger.info
        log(f"[{real_ip}] - RQ: {self.command} {self.path}: {endpoint_exec_result['rc']}. Data: TX:{size}b")
        logger.debug(f"RQ Headers: {self.headers}")
        if binary:
            logger.debug("Data omitted: binary.")
        elif size < 8192:
            logger.debug(f"Data: {body.decode('utf-8', errors='replace')}")
        else:
            logger.debug("Data omitted: too big.")

    def do_GET(self):
        try:
            ip_from_headers = self.headers.get('X-Real-IP')
            if ip_from_headers is not None:
                self.client_address = (ip_from_headers, self.client_address[1])
            parsed = urlsplit(self.path)
            path = parsed.path
            if path in ws_endpoints.get("GET", {}):
                self.error(
                    426,
                    f"This endpoint is a WebSocket. Connect to port {ws_listen_port()}.",
                )
                logger.info(f"[{self.client_address[0]}] - RQ: GET {path}: 426")
                return
            if path in endpoints["GET"]:
                query = {
                    key: values[0] if len(values) == 1 else values
                    for key, values in parse_qs(parsed.query, keep_blank_values=True).items()
                }
                fn = endpoints["GET"][path]
                if query:
                    endpoint_exec_result = fn(self.headers, query)
                else:
                    endpoint_exec_result = fn(self.headers)
                self._write_endpoint_result(path, endpoint_exec_result)
            else:
                self.error(404, f"No such endpoint: '{path}'")
                logger.info(f"RQ: GET {self.path}: 404")
        except Exception as e:
            try:
                self.error(500, f"Server error: {e.__class__.__name__}")
            except:
                pass
            logger.error(f"RQ: GET {self.path}: 500 ({e.__class__.__name__})")
            logger.exception(e)

    def do_POST(self):
        try:
            ip_from_headers = self.headers.get('X-Real-IP')
            if ip_from_headers is not None:
                self.client_address = (ip_from_headers, self.client_address[1])
            if self.path in endpoints["POST"]:
                data_length = int(self.headers.get('Content-Length'))
                if data_length > MAX_DATA_LEN:
                    self.send_response(413)
                    self._send_cors_headers()
                    self.end_headers()
                try:
                    data = json.loads(self.rfile.read(data_length).decode("utf-8"))
                except Exception:
                    self.error(400, "Malformed data")
                    return
                endpoint_exec_result = endpoints["POST"][self.path](self.headers, data)
                self._write_endpoint_result(self.path, endpoint_exec_result)
            else:
                self.error(404, f"No such endpoint: '{self.path}'")
                logger.info(f"RQ: POST {self.path}: 404")
        except Exception as e:
            try:
                self.error(500, f"Server error: {e.__class__.__name__}")
            except:
                pass
            logger.error(f"RQ: POST {self.path}: 500 ({e.__class__.__name__})")
            logger.exception(e)


class LoRadWSServer(LoRadAPIServer):
    def do_POST(self):
        self.error(405, "WebSocket port accepts GET upgrades only.")

    def do_GET(self):
        try:
            ip_from_headers = self.headers.get("X-Real-IP")
            if ip_from_headers is not None:
                self.client_address = (ip_from_headers, self.client_address[1])
            real_ip = self.headers.get("X-Real-IP") or self.client_address[0]
            fn = ws_endpoints.get("GET", {}).get(self.path)
            if fn is None:
                self.error(404, f"No such WebSocket: '{self.path}'")
                logger.info(f"[{real_ip}] - WS {self.path}: 404")
                return
            try:
                pre = fn(self.headers)
            except Exception as e:
                logger.exception(e)
                self.error(500, f"Server error: {e.__class__.__name__}")
                return
            if not isinstance(pre, dict) or not pre.get("websocket"):
                if isinstance(pre, dict) and "rc" in pre:
                    self.send_response(pre["rc"])
                    self.send_header("Content-type", pre.get("content-type", "application/json"))
                    self._send_cors_headers()
                    self.end_headers()
                    data = pre.get("data", {})
                    body = json.dumps(data) if isinstance(data, dict) else str(data)
                    self.wfile.write(body.encode("utf-8"))
                    self.wfile.flush()
                    return
                self.error(500, "Incorrect output from the endpoint function.")
                return
            if not is_websocket_upgrade(self.headers):
                self.error(426, "This endpoint is a WebSocket. Send Upgrade: websocket.")
                logger.info(f"[{real_ip}] - RQ: GET {self.path}: 426")
                return
            ws = WebSocket(self)
            if not ws.handshake():
                self.error(400, "Bad WebSocket handshake")
                logger.info(f"[{real_ip}] - RQ: GET {self.path}: 400 (websocket handshake)")
                return
            logger.info(f"[{real_ip}] - WS {self.path}: connected")
            try:
                fn(self.headers, ws)
            except Exception as e:
                logger.error(f"[{real_ip}] - WS {self.path}: {e.__class__.__name__}")
                logger.exception(e)
            finally:
                try:
                    if ws.open:
                        ws.close()
                except Exception:
                    pass
                logger.info(f"[{real_ip}] - WS {self.path}: disconnected")
        except Exception as e:
            try:
                self.error(500, f"Server error: {e.__class__.__name__}")
            except Exception:
                pass
            logger.error(f"WS: GET {self.path}: 500 ({e.__class__.__name__})")
            logger.exception(e)


def start_api_server():
    logger.info("Initializing LoRaD REST API...")
    register_endpoints()
    from lorad.api.utils.immich import start_immich_cache
    start_immich_cache()
    rest_port = rest_listen_port()
    ws_port = ws_listen_port()
    ws_server = ThreadingWSServer(("0.0.0.0", ws_port), LoRadWSServer)
    Thread(name="API-WS", target=ws_server.serve_forever, daemon=True).start()
    logger.info(f"REST listening on port {rest_port} (single-threaded).")
    logger.info(f"WebSocket listening on port {ws_port} (threaded).")
    HTTPServer(("0.0.0.0", rest_port), LoRadAPIServer).serve_forever()
