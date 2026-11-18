from fastapi import Depends, HTTPException, status

from database.models import User
from auth.dependencies import get_current_user
from auth.roles import UserRole

def require_roles(*allowed_roles: UserRole):
  def role_checker(
      current_user: User = Depends(get_current_user),
  )-> User:

    # Check whether the authenticated user has permission
    if current_user.role not in [
      role.value for role in allowed_roles
    ]:

      raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail = "You do not have permission to perform this action.",
      )

    return current_user

  return role_checker