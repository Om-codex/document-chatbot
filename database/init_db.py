from database.connection import Base, engine

# import models so SQLAlchemy registers them
from database.models import User

def init_database():
  Base.metadata.create_all(bind=engine)

  print("Database initialized successfully!")

if __name__ == "__main__":
  init_database() 