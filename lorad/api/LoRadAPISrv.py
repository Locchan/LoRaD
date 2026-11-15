from purest import configure, serve
from purest.server import APIServer as LoRadAPIServer
from purest.server import WSServer as LoRadWSServer
from purest.server import register_endpoints as _register_endpoints

from lorad.api.auth_backend import get_auth_backend
from lorad.common.utils.logger import get_logger
from lorad.common.utils.misc import feature_enabled, get_version, read_config

logger = get_logger()
config = read_config()


def rest_listen_port():
    return config["REST"]["LISTEN_PORT"]


def ws_listen_port():
    return config["REST"].get("WS_LISTEN_PORT", 5478)


def _configure_purest():
    configure(
        logger=logger,
        max_data_len_bytes=config["REST"]["MAX_DATA_LEN_BYTES"],
        server_version=f"LoRaD API v.{get_version()}",
        auth_backend=get_auth_backend(),
        feature_enabled=feature_enabled,
        debug_quiet_paths=["/whatsplaying"],
        openapi_title="LoRaD rest API",
        openapi_version="1.0.0",
    )


def register_endpoints():
    _configure_purest()
    import lorad.api.endpoints

    return _register_endpoints(lorad.api.endpoints.endpoints_to_register)


def start_api_server():
    _configure_purest()
    import lorad.api.endpoints

    def on_start():
        from lorad.api.utils.immich import start_immich_cache
        start_immich_cache()

    serve(
        rest_listen_port(),
        ws_listen_port(),
        lorad.api.endpoints.endpoints_to_register,
        on_start=on_start,
    )


__all__ = [
    "LoRadAPIServer",
    "LoRadWSServer",
    "register_endpoints",
    "rest_listen_port",
    "start_api_server",
    "ws_listen_port",
]
