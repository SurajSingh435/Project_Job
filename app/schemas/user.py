from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    """Payload required to register a new user."""
    name: str = Field(..., min_length=1, max_length=100, examples=["Jane Doe"])
    email: EmailStr = Field(..., examples=["jane@example.com"])
    password: str = Field(..., min_length=8, description="Plain-text password (hashed server-side)")
    role: UserRole = Field(default=UserRole.resident)


class UserLogin(BaseModel):
    """Credentials for session-cookie login."""
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """Fields that a user (or admin) may update."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class UserRead(BaseModel):
    """Safe user representation — never exposes password_hash."""
    id: str = Field(..., alias="_id", description="MongoDB ObjectId as string")
    name: str
    email: EmailStr
    role: UserRole
    created_at: datetime

    model_config = {"populate_by_name": True, "from_attributes": True}
