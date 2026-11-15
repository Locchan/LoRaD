from purest.auth import GroupMixin

from lorad.common.database.Base import Base


class Group(GroupMixin, Base):
    __tablename__ = "api_group"
