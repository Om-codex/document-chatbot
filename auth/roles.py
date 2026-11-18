from enum import Enum

class UserRole(str, Enum):
  ADMIN = "admin"
  EDITOR = "editor"
  VIEWER = "viewer"