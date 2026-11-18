from datetime import datetime, timedelta, timezone
import jwt
from jwt.exceptions import InvalidTokenError
from config.settings import settings

# Fixed signing algortihm
JWT_ALGORITHM = "HS256"

def create_access_token(
    user_id: int,
)->str:
  """
  Generate a signed JWT access token for an authenticated user.
  """

  # Retrieve JWT secret
  if settings.jwt_secret_key is None:
    raise RuntimeError("JWT_SECRET_KEY must contain at least 32 bytes")

  secret_key = settings.jwt_secret_key.get_secret_value()

  # Token timestamps
  issued_at = datetime.now(timezone.utc)

  expires_at = issued_at + timedelta(
    minutes = settings.jwt_access_token_expire_minutes
  )

  # JWT payload
  payload = {
    "sub": str(user_id),
    "iat": issued_at,
    "exp": expires_at,
  }

  # Generate signed JWT
  token = jwt.encode(
    payload,
    secret_key,
    algorithm = JWT_ALGORITHM
  )

  return token

def verify_access_token(token: str) -> dict | None:
  """
  Verify JWT signature and expiration.
  
  Returns decoded claims if valid.
  Returns None if invalid or expired.
  """

  if settings.jwt_secret_key is None:
    raise RuntimeError("JWT_SECRET_KEY is not configured")

  secret_key = settings.jwt_secret_key.get_secret_value()

  if len(secret_key.encode("utf-8")) < 32:
    raise RuntimeError(
      "JWT_SECRET_KEY must contain at least 32 bytes"
    )

  try:
    payload = jwt.decode(
      token,
      secret_key,
      algorithms=[JWT_ALGORITHM],
      options={
        "require": ["exp","iat","sub"]
      },
    )

    # Validate subject
    user_id = payload.get("sub")

    if not isinstance(user_id, str) or not user_id.isdecimal():
      return None

    if int(user_id) <= 0:
      return None

    return payload
  
  except InvalidTokenError:
    return None