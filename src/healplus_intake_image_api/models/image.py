from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from healplus_intake_image_api.core.database import Base


class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))