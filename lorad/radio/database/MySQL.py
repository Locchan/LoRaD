# pylint: disable=invalid-name
''' Main database connector. All the code that uses the database uses this to connect.'''

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session
from lorad.radio.database.Base import Base
from lorad.common.utils.utils import read_config
from lorad.common.utils.logger import get_logger

logger = get_logger()

class MySQL():
    '''Connector class. The connector engine itself is static'''
    engine = None
    obj = None
    
    def __init__(self) -> None:
        self.__reconnect()
        self._register_orm()
        MySQL.obj = self

    def _get_session(self) -> Session:
        return sessionmaker(autoflush=True, bind=MySQL.engine)()

    def _register_orm(self):
        from lorad.radio.programs.news.orm.News import News
        Base.metadata.create_all(MySQL.engine)

    def __reconnect(self) -> None:
        if MySQL.engine is None:
            connection_string = self.__generate_connection_string()
            MySQL.engine = create_engine(connection_string, pool_pre_ping=True)

    def __generate_connection_string(self) -> str:
        config = read_config()
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