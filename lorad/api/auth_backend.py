"""LoRaD wiring for purest's MysqlAuthBackend."""

from purest.auth import MysqlAuthBackend

import lorad.common.utils.globs as globs
from lorad.common.database.Base import Base
from lorad.common.database.MySQL import MySQL
from lorad.common.utils.logger import get_logger
from lorad.common.utils.misc import read_config

# Do not change: existing password rows are hashed with this salt.
PASSWORD_SALT = "Mei8HrFsNkEnEXs$J5#q22DA4hdZZ#4964EEvYL2$4G4WDRBJ%z&&Nfg8&EBxRHK"

_backend: MysqlAuthBackend | None = None


def get_auth_backend() -> MysqlAuthBackend:
    global _backend
    if _backend is None:
        config = read_config()
        _backend = MysqlAuthBackend(
            Base,
            session_factory=MySQL.get_session,
            salt=PASSWORD_SALT,
            token_ttl_min=config["REST"]["TOKEN_EXPIRATION_MIN"],
            bypass_cap=globs.CAP_IMBA,
            default_group_name="default",
            default_capabilities=globs.CAP_BASIC_USER,
            logger=get_logger(),
        )
    return _backend
