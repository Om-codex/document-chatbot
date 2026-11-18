from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator

class UserRegister(BaseModel):

  """Incoming Registration data"""

  email : EmailStr # simple EmailStr validator

  password : str = Field(
    min_length = 8,
    max_length = 128,
  )

  @field_validator("email", mode="before")
  @classmethod
  def normalize_email(cls, value):
    if isinstance(value, str):
      return value.strip().lower()

    return value

class UserResponse(BaseModel):
  """Public user information returned by the API"""

  model_config = ConfigDict(from_attributes=True)

  id: int
  email: EmailStr
  role : str
  is_active: bool

class UserLogin(BaseModel):
  """Incoming user credentials."""

  email : EmailStr

  password : str = Field(
    min_length = 8,
    max_length = 128,
  )

  @field_validator("email", mode = "before")
  @classmethod
  def normalize_email(cls, value):
    if isinstance(value, str):
      return value.strip().lower()
    return value

class LoginResponse(BaseModel):
  """Sucessfull login response."""

  message: str
  access_token: str
  token_type: str = "bearer"
  user: UserResponse