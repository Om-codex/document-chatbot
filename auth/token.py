from datetime import datetime, timedelta, timezone
import jwt
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