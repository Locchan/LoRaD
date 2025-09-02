from sqlalchemy import ForeignKey, String, delete, select
from sqlalchemy.orm import Mapped, mapped_column

from lorad.api.utils.misc import hash_password
from lorad.common.database.Base import Base
from lorad.common.database.MySQL import MySQL
import lorad.common.utils.globs as globs
from lorad.common.utils.logger import get_logger

logger = get_logger()

class User(Base):
    __tablename__ = "api_user"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(16), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    group: Mapped[str] = mapped_column(ForeignKey("api_group.id"))

def user_register(username, password) -> bool:
    from lorad.api.orm.Group import Group
    with MySQL.get_session() as session:
        user_obj = session.scalar(select(User).where(User.name == username))
        if user_obj is not None:
            return False
        default_group = session.scalar(select(Group).where(Group.name == "default"))
        if default_group is None:
            default_group = Group(name="default", capabilities=globs.CAP_BASIC_USER)
            session.add(default_group)
        new_user_obj = User(name=username, password_hash=hash_password(password), group=default_group.id)
        session.add(new_user_obj)
        session.commit()
        logger.info(f"Registered user: {username}")
        return True

def user_remove(username) -> bool:
    from lorad.api.orm.Token import Token
    with MySQL.get_session() as session:
        user_obj = session.scalar(select(User).where(User.name == username))
        if user_obj is None:
            return False
        res = session.execute(delete(Token).where(Token.user == user_obj.id))
        count = res.rowcount
        session.delete(user_obj)
        session.commit()
        logger.info(f"Deleted user '{username}'. Invalidated {count} associated tokens.")
        return True

def user_login(username, password_to_check) -> int:
    with MySQL.get_session() as session:
        user = session.scalar(select(User).where(User.name == username))
        if user is None:
            return globs.LOGIN_NO_SUCH_USER
        password_to_check_hash = hash_password(password_to_check)
        if user.password_hash == password_to_check_hash:
            return globs.LOGIN_SUCCESS
        return globs.LOGIN_INCORRECT_PASSWORD
