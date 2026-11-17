from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from database.models import User
from schemas.auth import UserRegister
from auth.security import hash_password

def register_user(
    db: Session,
    user_data: UserRegister,
)-> User:

  # 1. Check whether email already exists
  existing_user = db.scalar(
    select(User).where(
      User.email == str(user_data.email)
    )
  )

  if existing_user:
    raise ValueError("Email is already registered.")

  # 2. Hash the password
  hashed_password = hash_password(user_data.password)

  # 3. Create User Object
  new_user = User(
    email = str(user_data.email),
    hashed_password = hashed_password,
    role = "User",
  )

  # 4. Save user to database
  try:
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

  except IntegrityError:
    db.rollback()
    raise ValueError("Email is already registered!")

  return new_user