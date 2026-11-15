"""LoRaD aliases for purest decorators (keeps @lrd_* names in endpoints)."""

from purest.decorators import api_endp as lrd_api_endp
from purest.decorators import auth as lrd_auth
from purest.decorators import feat_req as lrd_feat_req
from purest.decorators import validate as lrd_validate
from purest.decorators import websocket as lrd_websocket

__all__ = [
    "lrd_api_endp",
    "lrd_auth",
    "lrd_feat_req",
    "lrd_validate",
    "lrd_websocket",
]
