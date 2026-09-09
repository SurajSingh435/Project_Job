from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.complaint import ComplaintStatus


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class ComplaintCreate(BaseModel):
    """Payload submitted by a resident to file a new complaint."""
    category: str = Field(..., min_length=1, max_length=100, examples=["road"])
    description: str = Field(
        ..., min_length=10, max_length=5000,
        examples=["Large pothole on Main Street near bus stop 12."],
    )


class StatusUpdate(BaseModel):
    """Admin-only: change the status of a complaint."""
    status: ComplaintStatus = Field(..., description="New status value")


class ComplaintUpdate(BaseModel):
    """
    General-purpose update schema used by the AI pipeline or admin bulk edits.
    Residents never send this directly.
    """
    category: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, min_length=10, max_length=5000)
    status: Optional[ComplaintStatus] = None

    # AI-enriched fields
    embedding: Optional[List[float]] = None
    ai_title: Optional[str] = Field(default=None, max_length=200)
    ai_urgency: Optional[str] = None
    ai_reasoning: Optional[str] = None

    # Duplicate detection
    duplicate_of: Optional[str] = Field(
        default=None, description="ObjectId string of the original complaint",
    )
    similarity_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class ComplaintRead(BaseModel):
    """Full complaint representation returned to API consumers."""
    id: str = Field(..., alias="_id", description="MongoDB ObjectId as string")
    resident_id: str = Field(..., description="ObjectId of the resident who filed the complaint")

    category: str
    description: str
    status: ComplaintStatus

    embedding: List[float] = Field(default_factory=list)
    ai_title: Optional[str] = None
    ai_urgency: Optional[str] = None
    ai_reasoning: Optional[str] = None

    duplicate_of: Optional[str] = Field(
        default=None, description="ObjectId of the original complaint if duplicate",
    )
    similarity_score: Optional[float] = None

    created_at: datetime
    updated_at: datetime

    model_config = {"populate_by_name": True, "from_attributes": True}


class ComplaintListRead(BaseModel):
    """Lightweight list-item representation (omits the heavy embedding vector)."""
    id: str = Field(..., alias="_id")
    resident_id: str
    category: str
    status: ComplaintStatus
    ai_title: Optional[str] = None
    ai_urgency: Optional[str] = None
    duplicate_of: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"populate_by_name": True, "from_attributes": True}
