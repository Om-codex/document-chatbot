from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from database.models import User
from schemas.auth import UserRegister
from auth.security import hash_password
from auth.security import verify_password

# to register the new user
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

# to authenticate existing user
def authenticate_user(
  db: Session,
  email: str,
  password: str,
)->User | None :
  """
  Authenticate a user using email and password.
  
  Returns the User object if credentials are valid.
  
  Otherwise returns None."""

  # 1. Find the existing user by email
  user = db.scalar(
    select(User).where(User.email == email)
  )

  # 2. User does not exist
  if user is None:
    return None

  # 3. Verify submitted password against stored hash
  if not verify_password(password, user.hashed_password):
    return None

  # 4. Check account status
  if not user.is_active:
    return None

  return user