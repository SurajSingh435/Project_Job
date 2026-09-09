from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from beanie import Document
from pydantic import EmailStr, Field


class UserRole(str, Enum):
    resident = "resident"
    admin = "admin"


class User(Document):
    """Beanie ODM document for application users."""

    name: str = Field(..., min_length=1, max_length=100, description="Full name of the user")
    email: EmailStr = Field(..., description="Unique email address")
    password_hash: str = Field(..., description="Bcrypt-hashed password")
    role: UserRole = Field(default=UserRole.resident, description="User role")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the account was created",
    )

    class Settings:
        name = "users"
        indexes = [
            "email",  # unique index defined below via pymongo index model
        ]

    class Config:
        # Allow population by field name when using .model_dump()
        populate_by_name = True
