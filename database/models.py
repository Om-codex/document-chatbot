from datetime import datetime, timezone

from sqlalchemy import (
  String, Integer, Boolean, DateTime,
)

from sqlalchemy.orm import Mapped, mapped_column
from database.connection import Base

class User(Base):

  __tablename__ = "users"

  # Primary Key
  id: Mapped[int] = mapped_column(
    Integer,
    primary_key=True,
    index = True,
  )

  # User Email
  email: Mapped[str] = mapped_column(
    String(320),
    unique = True,
    index = True,
    nullable = False,
  )

  # Hashed Password
  hashed_password: Mapped[str] = mapped_column(
    String(255),
    nullable = False,
  )

  # User Role
  role: Mapped[str] = mapped_column(
    String(50),
    default = "user",
    nullable = False,
  )

  # Account Status
  is_active: Mapped[bool] = mapped_column(
    Boolean,
    default = True,
    nullable = False,
  )

  # Account Creation TimeStamp
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone = True),
    default = lambda: datetime.now(timezone.utc),
    nullable = False
  )