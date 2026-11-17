from pwdlib import PasswordHash

# Create the recommended password hashing configuration()
password_hash = PasswordHash.recommended()

def hash_password(password: str) -> str:
  """"
  Hash a plain-text password using Argon2id.
  """

  if not password:
    raise ValueError("Password cannot be empty")

  return password_hash.hash(password)

def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
  """
  Verify a plain-text password against its stored hash.
  """

  if not plain_password or not hashed_password:
    return False

  return password_hash.verify(
    plain_password,
    hashed_password
  )