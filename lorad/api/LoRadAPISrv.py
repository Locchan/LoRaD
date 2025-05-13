from http.server import BaseHTTPRequestHandler, HTTPServer

from lorad.common.utils.logger import get_logger
from lorad.common.utils.utils import read_config

logger = get_logger()
config = read_config()

class LoRadAPIServer(BaseHTTPRequestHandler):
    # @staticmethod
    # def log_message(*args):
    #     pass

    def __init__(self, request, client_address, server):
        super().__init__(request, client_address, server)
        self.endpoints = register_endpoints()

    def do_GET(self):
        pass

def start_server():
    server = HTTPServer(("0.0.0.0", config["REST"]["LISTEN_PORT"]), LoRadAPIServer)
    server.serve_forever()
