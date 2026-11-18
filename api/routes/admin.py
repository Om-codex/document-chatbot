from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import User
from schemas.auth import UserResponse
from auth.permissions import require_roles
from auth.roles import UserRole

router = APIRouter(
  prefix="/admin",
  tags=["Admin"],
)

@router.get(
  "/users",
  response_model = list[UserResponse],
)
def get_all_users(
  db: Session = Depends(get_db),
  current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
  users = db.scalars(
    select(User).order_by(User.id)
  ).all()

  return users