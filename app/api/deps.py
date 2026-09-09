"""
app/api/deps.py — Reusable FastAPI dependency functions.

Auth is now HttpOnly session cookies backed by Starlette SessionMiddleware
(itsdangerous signed cookies). No JWT.
"""
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.models.user import User, UserRole


async def get_current_user(request: Request) -> User:
    """
    Read the user_id stored in the signed session cookie and return
    the corresponding User document from MongoDB.

    Raises 401 if the session is missing or the user no longer exists.
    """
    user_id: str | None = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    user = await User.get(user_id)
    if user is None:
        # Session is stale — clear it
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found — please log in again",
        )
    return user


async def require_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Raise 403 if the authenticated user is not an admin."""
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user
