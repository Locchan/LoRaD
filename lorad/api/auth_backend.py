"""LoRaD wiring for purest's SqlAlchemyAuthBackend."""

from purest.auth import SqlAlchemyAuthBackend

import lorad.common.utils.globs as globs
from lorad.common.database.MySQL import MySQL
from lorad.common.utils.logger import get_logger
from lorad.common.utils.misc import read_config

# Do not change: existing password rows are hashed with this salt.
PASSWORD_SALT = "Mei8HrFsNkEnEXs$J5#q22DA4hdZZ#4964EEvYL2$4G4WDRBJ%z&&Nfg8&EBxRHK"

_backend: SqlAlchemyAuthBackend | None = None


def get_auth_backend() -> SqlAlchemyAuthBackend:
    global _backend
    if _backend is None:
        from lorad.api.orm.Group import Group
        from lorad.api.orm.Token import Token
        from lorad.api.orm.User import User

        config = read_config()
        _backend = SqlAlchemyAuthBackend(
            MySQL.get_session,
            User,
            Group,
            Token,
            salt=PASSWORD_SALT,
            token_ttl_min=config["REST"]["TOKEN_EXPIRATION_MIN"],
            bypass_cap=globs.CAP_IMBA,
            default_group_name="default",
            default_capabilities=globs.CAP_BASIC_USER,
            logger=get_logger(),
        )
    return _backend
