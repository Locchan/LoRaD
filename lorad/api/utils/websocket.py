import base64
import hashlib
import json
import socket
import struct
import threading

from lorad.common.utils.logger import get_logger
from lorad.common.utils.misc import read_config

logger = get_logger()

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
OP_CONT = 0x0
OP_TEXT = 0x1
OP_BIN = 0x2
OP_CLOSE = 0x8
OP_PING = 0x9
OP_PONG = 0xA


def is_websocket_upgrade(headers) -> bool:
    upgrade = (headers.get("Upgrade") or "").lower()
    connection = (headers.get("Connection") or "").lower()
    return upgrade == "websocket" and "upgrade" in connection and bool(headers.get("Sec-WebSocket-Key"))


def accept_key(sec_key: str) -> str:
    digest = hashlib.sha1((sec_key.strip() + WS_GUID).encode("utf-8")).digest()
    return base64.b64encode(digest).decode("ascii")


class WebSocket:
    """One accepted WebSocket. Passed as the second argument of impl_GET."""

    def __init__(self, request):
        self.request = request
        self.sock = request.connection
        self.open = False
        self._send_lock = threading.Lock()
        self._max = int(read_config().get("REST", {}).get("MAX_DATA_LEN_BYTES", 1024000))

    def handshake(self) -> bool:
        headers = self.request.headers
        if (headers.get("Sec-WebSocket-Version") or "13") != "13":
            return False
        key = headers.get("Sec-WebSocket-Key")
        if not key:
            return False
        # Written by hand: BaseHTTPRequestHandler would answer HTTP/1.0 and browsers
        # only accept a 101 upgrade over HTTP/1.1.
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_key(key)}\r\n"
            "\r\n"
        )
        try:
            self.request.wfile.write(response.encode("ascii"))
            self.request.wfile.flush()
        except Exception:
            return False
        self.request.close_connection = True
        self.open = True
        return True

    def send(self, data):
        if isinstance(data, (dict, list)):
            data = json.dumps(data, ensure_ascii=False)
        if isinstance(data, str):
            logger.debug(f"WS TX {self.request.path}: {data}")
            return self._send_frame(OP_TEXT, data.encode("utf-8"))
        if isinstance(data, (bytes, bytearray)):
            logger.debug(f"WS TX {self.request.path}: {len(data)} bytes")
            return self._send_frame(OP_BIN, bytes(data))
        raise TypeError(f"Cannot send {type(data).__name__} over WebSocket")

    def recv(self, timeout=None):
        """Return str/bytes, or None on timeout / close."""
        if not self.open:
            return None
        previous = self.sock.gettimeout()
        try:
            self.sock.settimeout(timeout)
            while self.open:
                opcode, payload = self._recv_frame()
                if opcode is None:
                    return None
                if opcode == OP_PING:
                    self._send_frame(OP_PONG, payload)
                    continue
                if opcode == OP_PONG:
                    continue
                if opcode == OP_CLOSE:
                    self.close()
                    return None
                if opcode == OP_TEXT:
                    return payload.decode("utf-8")
                if opcode == OP_BIN:
                    return payload
        except socket.timeout:
            return None
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            self.open = False
            return None
        finally:
            try:
                self.sock.settimeout(previous)
            except Exception:
                pass
        return None

    def close(self):
        if not self.open:
            return
        self.open = False
        try:
            self._send_frame(OP_CLOSE, b"")
        except Exception:
            pass
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass

    def _send_frame(self, opcode: int, payload: bytes):
        if not self.open and opcode != OP_CLOSE:
            return False
        header = bytearray([0x80 | (opcode & 0x0F)])
        n = len(payload)
        if n < 126:
            header.append(n)
        elif n < 65536:
            header.append(126)
            header.extend(struct.pack("!H", n))
        else:
            header.append(127)
            header.extend(struct.pack("!Q", n))
        with self._send_lock:
            self.sock.sendall(header + payload)
        return True

    def _recv_exact(self, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionResetError("socket closed")
            buf.extend(chunk)
        return bytes(buf)

    def _recv_frame(self):
        header = self._recv_exact(2)
        fin = header[0] & 0x80
        opcode = header[0] & 0x0F
        masked = header[1] & 0x80
        length = header[1] & 0x7F
        if not fin or opcode == OP_CONT:
            raise RuntimeError("Fragmented WebSocket frames are not supported")
        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]
        if length > self._max:
            self.close()
            raise RuntimeError("WebSocket frame too large")
        if not masked:
            self.close()
            raise RuntimeError("Client WebSocket frames must be masked")
        mask = self._recv_exact(4)
        payload = self._recv_exact(length) if length else b""
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        return opcode, payload
