from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import sys

from lorad.common.utils.logger import get_logger
from lorad.common.utils.misc import get_version, read_config

endpoints = {}
logger = get_logger()
config = read_config()
MAX_DATA_LEN = config["REST"]["MAX_DATA_LEN_BYTES"]

def register_endpoints():
    global endpoints
    logger.info("Registering API endpoints")
    import lorad.api.endpoints
    registered_endpoints = 0
    for endpoint_module in lorad.api.endpoints.endpoints_to_register:
        try:
            # To add support for other methods, specify them here and just implement impl_X methods in endpoint modules
            for amethod in ["GET", "POST"]:
                if amethod not in endpoints:
                    endpoints[amethod] = {}

                # If the endpoint module does not have impl_{amethod}, continue to look for other methods
                try:
                    getattr(endpoint_module, f"impl_{amethod}")
                except AttributeError:
                    continue

                logger.debug(f"Registering: {amethod} - {endpoint_module.ENDP_PATH}")

                if endpoint_module.ENDP_PATH not in endpoints[amethod]:
                    endpoints[amethod][endpoint_module.ENDP_PATH] = getattr(endpoint_module, f"impl_{amethod}")
                    registered_endpoints+=1
                else:
                    logger.error(f"Could not register {amethod} endpoint from module {endpoint_module.__name__}: endpoint path already taken.")
                    os._exit(0)
        except Exception as e:
            logger.error(f"Could not register an endpoint: {endpoint_module.__name__}")
            logger.exception(e)
            os._exit(0)
    logger.info(f"Registered {registered_endpoints} endpoints.")

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
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode("utf-8"))
        self.wfile.flush()

    def do_GET(self):
        try:
            if self.path in endpoints["GET"]:
                endpoint_exec_result = endpoints["GET"][self.path](self.headers)
                self.send_response(endpoint_exec_result["rc"])
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                if isinstance(endpoint_exec_result["data"], dict):
                    response = json.dumps(endpoint_exec_result["data"])
                else:
                    response = endpoint_exec_result["data"]
                self.wfile.write(response.encode("utf-8"))
                self.wfile.flush()
                logger.info(f"RQ: GET {self.path}: {endpoint_exec_result["rc"]}." +
                            f" Data: TX:{sys.getsizeof(response)}b")
                logger.debug(f"RQ Headers: {self.headers}")
                if sys.getsizeof(response) < 8192:
                    logger.debug(f"Data: {response}")
                else:
                    logger.debug(f"Data omitted: too big.")
            else:
                self.error(404, f"No such endpoint: '{self.path}'")
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
            if self.path in endpoints["POST"]:
                data_length = int(self.headers.get('Content-Length'))
                if data_length > MAX_DATA_LEN:
                    self.send_response(413)
                    self.end_headers()
                try:
                    data = json.loads(self.rfile.read(data_length).decode("utf-8"))
                except Exception:
                    self.error(400, "Malformed data")
                    return
                endpoint_exec_result = endpoints["POST"][self.path](self.headers, data)
                self.send_response(endpoint_exec_result["rc"])
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                if isinstance(endpoint_exec_result["data"], dict):
                    response = json.dumps(endpoint_exec_result["data"])
                else:
                    response = endpoint_exec_result["data"]
                self.wfile.write(response.encode("utf-8"))
                self.wfile.flush()
                logger.info(f"RQ: POST {self.path}: {endpoint_exec_result["rc"]}." +
                            f" Data: RX:{data_length}b" +
                            f" TX:{sys.getsizeof(endpoint_exec_result["data"])}b")
                logger.debug(f"RQ Headers: {self.headers}")
                logger.debug(f"Data: {response}")
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

def start_api_server():
    global endpoints
    logger.info("Initializing LoRaD REST API...")
    server = HTTPServer(("0.0.0.0", config["REST"]["LISTEN_PORT"]), LoRadAPIServer)
    register_endpoints()
    logger.info(f"Ready. Listening on port {config["REST"]["LISTEN_PORT"]}.")
    server.serve_forever()
