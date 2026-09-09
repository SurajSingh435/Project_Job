"""
app/api/auth.py — Registration, login, and logout endpoints.

Uses HttpOnly session cookies (Starlette SessionMiddleware).
No JWT involved.
"""
from fastapi import APIRouter, HTTPException, Request, Response, status

from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, UserRead
from app.services.auth_service import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate) -> User:
    """
    Create a new user account.

    - Hashes the password with bcrypt before saving.
    - Does NOT log the user in automatically; call /auth/login afterwards.
    - Returns 409 if the e-mail is already registered.
    """
    existing = await User.find_one(User.email == payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    await user.insert()
    return user


@router.post("/login", response_model=UserRead)
async def login(payload: UserLogin, request: Request) -> User:
    """
    Authenticate with e-mail + password.

    On success, writes the user_id into the signed, HttpOnly session
    cookie that Starlette manages — no JWT is issued.

    Returns the authenticated user's public profile.
    """
    user = await User.find_one(User.email == payload.email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # Store only the user_id in the session — never the password hash
    request.session["user_id"] = str(user.id)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request) -> None:
    """
    Clear the session cookie, effectively logging the user out.

    Always returns 204 — even if the user wasn't logged in.
    """
    request.session.clear()
