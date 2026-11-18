from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import User
from auth.token import verify_access_token

# Extract Bearer token from authorization header
bearer_scheme = HTTPBearer(auto_error=False)

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db)
)->User:
  """
  Extract JWT, verify it, and retrieve the authenticated user.
  """

  # 1. Check whether the Authorization header exists
  if credentials is None or credentials.scheme.lower() != "bearer":
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Authentication required",
      headers = {"WWW-Authenticate":"Bearer"},
    )

  # 2. Extract JWT
  token = credentials.credentials

  # 3. Verify JWT
  payload = verify_access_token(token)

  if payload is None:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Invalid or expired token",
      headers={"WWW-Authenticate": "Bearer"}
    )

  # 4. Extract user ID
  try:
    user_id = int(payload["sub"])
  except (KeyError, TypeError, ValueError):
    raise HTTPException(401, "Invalid token payload", headers={"WWW-Authenticate": "Bearer"})

  # 5. Retrieve user from database
  user = db.get(User, user_id)

  if user is None:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="User not found",
      headers={"WWW-Authenticate": "Bearer"},
    )

  # 6. Check account status
  if not user.is_active:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="User account is inactive",
      headers={"WWW-Authenticate": "Bearer"},
    )

  # 7. Return authenticated user
  return user