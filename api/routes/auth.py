from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database.connection import get_db
from schemas.auth import UserRegister, UserResponse, UserLogin, LoginResponse
from services.auth_services import register_user, authenticate_user
from auth.token import create_access_token
from auth.dependencies import get_current_user
from database.models import User

router = APIRouter(
  prefix="/auth",
  tags = ["Authentication"]
)

@router.post(
  "/register",
  response_model = UserResponse,
  status_code = status.HTTP_201_CREATED,
)

def register(
  user_data: UserRegister,
  db: Session = Depends(get_db),
):
  try:
    new_user = register_user(db, user_data)

    return new_user

  except ValueError as exc:
    raise HTTPException(
      status_code=status.HTTP_409_CONFLICT,
      detail = str(exc)
    )

@router.post(
  "/login",
  response_model = LoginResponse,
  status_code = status.HTTP_200_OK,
)
def login(
  credentials: UserLogin,
  db: Session = Depends(get_db),
):
  # 1. Authenticate the User
  user = authenticate_user(
    db = db,
    email = str(credentials.email),
    password = credentials.password,
  )

  # 2. Reject Invalid credentials
  if user is None:
    raise HTTPException(
      status_code = status.HTTP_401_UNAUTHORIZED,
      detail = "Invalid Email or Password!"
    )

  # 3. Generate JWT access token
  access_token = create_access_token(
    user_id = user.id,
  )

  # 4. Return public user information
  return {
    "message" : "Login successfull",
    "access_token": access_token,
    "token_type": "bearer",
    "user" : user
  }


@router.get(
  "/me",
  response_model=UserResponse,
)
def get_profile(
  current_user: User = Depends(get_current_user),
):
  """
  Return information about the authenticated user.
  """
  return current_user
