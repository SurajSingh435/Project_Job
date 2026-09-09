"""
app/api/users.py — User profile endpoints.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_admin, get_current_user
from app.models.user import User
from app.schemas.user import UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserRead)
async def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """Return the currently authenticated user."""
    return current_user


@router.patch("/me", response_model=UserRead)
async def update_me(
    payload: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Update the current user's own profile."""
    update_data = payload.model_dump(exclude_unset=True)
    # Residents must not be able to promote themselves
    if "role" in update_data:
        update_data.pop("role")
    await current_user.set(update_data)
    return current_user


@router.get("/{user_id}", response_model=UserRead, dependencies=[Depends(get_current_admin)])
async def get_user(user_id: str) -> User:
    """Admin-only: fetch any user by ID."""
    user = await User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user
