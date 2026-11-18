from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database.connection import get_db
from schemas.auth import UserRegister, UserResponse, UserLogin, LoginResponse
from services.auth_services import register_user, authenticate_user

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
  # Authenticate the User
  user = authenticate_user(
    db = db,
    email = str(credentials.email),
    password = credentials.password,
  )

  # Reject Invalid credentials
  if user is None:
    raise HTTPException(
      status_code = status.HTTP_401_UNAUTHORIZED,
      detail = "Invalid Email or Password!"
    )

  # Return public user information
  return {
    "message" : "Login successfull",
    "user" : user
  }