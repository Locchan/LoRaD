import datetime
import secrets
from zoneinfo import ZoneInfo
from sqlalchemy import DateTime, ForeignKey, String, select
from sqlalchemy.orm import Mapped, mapped_column

from lorad.api.orm.Group import Group
from lorad.api.orm.User import User
from lorad.common.database.Base import Base
from lorad.common.database.MySQL import MySQL
import lorad.common.utils.globs as globs
from lorad.common.utils.misc import read_config

config = read_config()
expiration_time_min = config["REST"]["TOKEN_EXPIRATION_MIN"]

class Token(Base):
    __tablename__ = "api_token"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(32), nullable=False)
    user: Mapped[str] = mapped_column(ForeignKey("api_user.id"), nullable=False)
    date_gen: Mapped[str] = mapped_column(DateTime, nullable=False)

def gen_token(username):
    token_str = secrets.token_hex(16)
    with MySQL.get_session() as session:
        user_obj = session.scalar(select(User).where(User.name == username))
        token_obj = Token(token=token_str, user=user_obj.id, date_gen=datetime.datetime.now(datetime.timezone.utc))
        session.add(token_obj)
        session.commit()
    return token_str

def validate_token(username, token) -> int:
    with MySQL.get_session() as session:
        user_obj = session.scalar(select(User).where(User.name == username))
        if user_obj is None:
            return False # No such user
        token_obj = session.scalar(select(Token).where(Token.token == token))
        if token_obj is None:
            return False # Wrong token
        if token_obj.user == user_obj.id:
            if token_obj.date_gen.replace(tzinfo=ZoneInfo("UTC")) + datetime.timedelta(minutes=expiration_time_min) < datetime.datetime.now(datetime.timezone.utc):
                return False # Token expired
            return True # Good!
        return False # There is such token but it does not belong to the user

def check_caps(username, needed_cap):
    with MySQL.get_session() as session:
        user = session.scalar(select(User).where(User.name == username))
        existing_caps = session.scalar(select(Group).where(Group.id == user.group)).capabilities
        if globs.CAP_IMBA in existing_caps:
            return True
        if existing_caps is not None:
            caps = existing_caps.split(",")
            return needed_cap in caps
        return False