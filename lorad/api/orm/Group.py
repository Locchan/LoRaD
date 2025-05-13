from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lorad.common.database.Base import Base


class Group(Base):
    __tablename__ = "api_group"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(16), nullable=False)
    capabilities: Mapped[str] = mapped_column(Text, nullable=False)
