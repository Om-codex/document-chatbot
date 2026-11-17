from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config.settings import settings

# Databse URL from application settings
DATABASE_URL = settings.database_url

# SQLite-specific configuration
connect_args = ()

if DATABASE_URL.startswith("sqlite"):
  connect_args = {"check_same_thread": False}

  # Create databse directory if it doesn't exist
  from pathlib import Path

  db_path = Path(DATABASE_URL.replace("sqlite:///","",1))
  db_path.parent.mkdir(parents = True, exist_ok = True)

# create the database engine
engine = create_engine(
  DATABASE_URL,
  connect_args=connect_args,
)


# Database session factory
SessionLocal = sessionmaker(
  bind = engine,
  autoflush = False,
  autocommit = False
)

# Base class for all database models
class Base(DeclarativeBase):
  pass