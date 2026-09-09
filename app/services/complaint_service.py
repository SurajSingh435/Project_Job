"""
app/services/complaint_service.py — Business logic for complaint CRUD.
"""
from datetime import datetime, timezone
from typing import List, Optional

from beanie import PydanticObjectId

from app.models.complaint import Complaint, ComplaintStatus
from app.models.user import User
from app.schemas.complaint import ComplaintCreate, ComplaintUpdate


async def create_complaint(data: ComplaintCreate, resident: User) -> Complaint:
    complaint = Complaint(
        resident_id=resident,  # type: ignore[arg-type]
        category=data.category,
        description=data.description,
    )
    await complaint.insert()
    return complaint


async def get_complaint(complaint_id: str) -> Optional[Complaint]:
    return await Complaint.get(PydanticObjectId(complaint_id))


async def list_complaints(
    status: Optional[ComplaintStatus] = None,
    resident_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
) -> List[Complaint]:
    query: dict = {}
    if status:
        query["status"] = status
    if resident_id:
        query["resident_id.$id"] = PydanticObjectId(resident_id)
    return await Complaint.find(query).skip(skip).limit(limit).to_list()


async def update_complaint(complaint: Complaint, data: ComplaintUpdate) -> Complaint:
    update_data = data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.now(timezone.utc)

    # Handle duplicate_of as a Link reference
    if "duplicate_of" in update_data and update_data["duplicate_of"] is not None:
        original = await Complaint.get(PydanticObjectId(update_data.pop("duplicate_of")))
        update_data["duplicate_of"] = original

    await complaint.set(update_data)
    return complaint


async def delete_complaint(complaint: Complaint) -> None:
    await complaint.delete()
