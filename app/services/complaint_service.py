"""
app/services/complaint_service.py — Business logic for complaint CRUD.
"""
from datetime import datetime, timezone
from typing import List, Optional

from beanie import PydanticObjectId
from pymongo import DESCENDING

from app.models.complaint import Complaint, ComplaintStatus
from app.models.user import User
from app.schemas.complaint import ComplaintCreate, ComplaintUpdate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resident_link_filter(resident_id: str) -> dict:
    """
    Build a MongoDB filter that matches the Beanie Link field resident_id.

    Beanie stores Link[User] as a DBRef: { "$ref": "users", "$id": ObjectId }.
    Querying by "$id" sub-field works reliably across Motor/Beanie versions.
    """
    return {"resident_id.$id": PydanticObjectId(resident_id)}


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

from app.services.ai_service import triage_complaint

async def create_complaint(data: ComplaintCreate, resident: User) -> Complaint:
    """Insert and return a new Complaint for *resident*."""
    triage_info = await triage_complaint(data.description, data.category)
    
    complaint = Complaint(
        resident_id=resident,  # type: ignore[arg-type]
        category=triage_info.get("corrected_category", data.category),
        description=data.description,
        ai_title=triage_info.get("clean_title"),
        ai_urgency=triage_info.get("urgency"),
        ai_reasoning=triage_info.get("reasoning")
    )
    await complaint.insert()
    return complaint


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

async def get_complaint_by_id(complaint_id: str) -> Optional[Complaint]:
    """Return the Complaint with *complaint_id*, or None if not found."""
    try:
        oid = PydanticObjectId(complaint_id)
    except Exception:
        return None
    return await Complaint.get(oid)


async def list_my_complaints(
    resident_id: str,
    skip: int = 0,
    limit: int = 20,
) -> List[Complaint]:
    """Return complaints filed by *resident_id*, newest first."""
    return (
        await Complaint.find(_resident_link_filter(resident_id))
        .sort([("created_at", DESCENDING)])
        .skip(skip)
        .limit(limit)
        .to_list()
    )


async def list_all_complaints(
    status: Optional[ComplaintStatus] = None,
    category: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> List[Complaint]:
    """
    Return all complaints (admin view), newest first.

    Optionally filtered by *status* and/or *category* (case-insensitive prefix match).
    """
    query: dict = {}
    if status:
        query["status"] = status.value
    if category:
        # Case-insensitive exact match; use a regex for prefix/fuzzy if preferred
        query["category"] = {"$regex": f"^{category}$", "$options": "i"}

    return (
        await Complaint.find(query)
        .sort([("created_at", DESCENDING)])
        .skip(skip)
        .limit(limit)
        .to_list()
    )


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

async def update_status(complaint: Complaint, new_status: ComplaintStatus) -> Complaint:
    """Change only the *status* field and refresh *updated_at*."""
    await complaint.set({
        "status": new_status,
        "updated_at": datetime.now(timezone.utc),
    })
    return complaint


async def update_complaint(complaint: Complaint, data: ComplaintUpdate) -> Complaint:
    """
    General-purpose update used by the AI pipeline or admin bulk edits.
    Residents never reach this path directly.
    """
    update_data = data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.now(timezone.utc)

    # Resolve duplicate_of string ? Link
    if "duplicate_of" in update_data and update_data["duplicate_of"] is not None:
        original = await get_complaint_by_id(update_data.pop("duplicate_of"))
        update_data["duplicate_of"] = original

    await complaint.set(update_data)
    return complaint


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

async def delete_complaint(complaint: Complaint) -> None:
    await complaint.delete()
