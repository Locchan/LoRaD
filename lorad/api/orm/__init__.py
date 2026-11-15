"""API auth ORM: models come from purest MysqlAuthBackend / create_mysql_auth_models."""

from purest.auth import create_mysql_auth_models

from lorad.common.database.Base import Base

User, Group, Token = create_mysql_auth_models(Base)

__all__ = ["Group", "Token", "User"]
