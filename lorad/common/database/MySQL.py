# pylint: disable=invalid-name
''' Main database connector. All the code that uses the database uses this to connect.'''

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session
from lorad.common.database.Base import Base
import lorad.common.utils.globs as globs
from lorad.common.utils.misc import feature_enabled, read_config
from lorad.common.utils.logger import get_logger

logger = get_logger()
config = read_config()

# Connector class. The connector engine itself is static
class MySQL():
    engine = None
    obj = None
    
    def __init__(self) -> None:
        logger.info("Connecting to the database...")
        self.__reconnect()
        self._register_orm()
        MySQL.obj = self

    def _get_session(self) -> Session:
        return sessionmaker(autoflush=True, bind=MySQL.engine)()

    def _register_orm(self):
        if feature_enabled(globs.FEAT_NEURONEWS):
            from lorad.audio.programs.news.orm.News import News
        if feature_enabled(globs.FEAT_REST):
            from lorad.api.orm.Group import Group
            from lorad.api.orm.User import User
        Base.metadata.create_all(MySQL.engine)

    def __reconnect(self) -> None:
        if MySQL.engine is None:
            connection_string = self.__generate_connection_string()
            MySQL.engine = create_engine(connection_string, pool_pre_ping=True)

    def __generate_connection_string(self) -> str:
        if "MYSQL" in config:
            try:
                c = config["MYSQL"]
                if "CHARSET" in c:
                    charset = c["CHARSET"]
                else:
                    charset = "utf8mb4"
                return f"mysql+pymysql://{c['USERNAME']}:{c['PASSWORD']}@{c['ADDRESS']}/{c['DATABASE']}?charset={charset}"
            except Exception as e:
                logger.error(f"Could not generate connection string: [{e.__class__.__name__}, {e}], something is missing in config.")
                os._exit(1)
        else:
            logger.error("No database credentials!")
            os._exit(1)

    @staticmethod
    def get_session() -> Session:
        if MySQL.obj is None:
            MySQL()
        return MySQL.obj._get_session()