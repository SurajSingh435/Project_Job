"""
app/api/complaints.py — Complaint CRUD endpoints.
"""
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_admin, get_current_user
from app.models.complaint import Complaint, ComplaintStatus
from app.models.user import User, UserRole
from app.schemas.complaint import (
    ComplaintCreate,
    ComplaintListRead,
    ComplaintRead,
    ComplaintUpdate,
)
from app.services.complaint_service import (
    create_complaint,
    delete_complaint,
    get_complaint,
    list_complaints,
    update_complaint,
)

router = APIRouter(prefix="/complaints", tags=["Complaints"])


@router.post("/", response_model=ComplaintRead, status_code=status.HTTP_201_CREATED)
async def submit_complaint(
    payload: ComplaintCreate,
    current_user: Annotated[User, Depends(get_current_user)],
) -> Complaint:
    """File a new complaint (any authenticated user)."""
    return await create_complaint(payload, current_user)


@router.get("/", response_model=List[ComplaintListRead])
async def list_all_complaints(
    current_user: Annotated[User, Depends(get_current_user)],
    complaint_status: Optional[ComplaintStatus] = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> List[Complaint]:
    """
    List complaints.
    - Admins see all complaints.
    - Residents see only their own.
    """
    resident_filter = None if current_user.role == UserRole.admin else str(current_user.id)
    return await list_complaints(
        status=complaint_status,
        resident_id=resident_filter,
        skip=skip,
        limit=limit,
    )


@router.get("/{complaint_id}", response_model=ComplaintRead)
async def get_one_complaint(
    complaint_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> Complaint:
    """Fetch a single complaint by ID."""
    complaint = await get_complaint(complaint_id)
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

    # Residents may only view their own complaints
    if current_user.role != UserRole.admin:
        owner_id = complaint.resident_id.ref.id if hasattr(complaint.resident_id, "ref") else str(complaint.resident_id)
        if str(owner_id) != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return complaint


@router.patch("/{complaint_id}", response_model=ComplaintRead)
async def patch_complaint(
    complaint_id: str,
    payload: ComplaintUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
) -> Complaint:
    """Update a complaint. Admins can update any field; residents can only edit their own open complaints."""
    complaint = await get_complaint(complaint_id)
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

    if current_user.role != UserRole.admin:
        owner_id = complaint.resident_id.ref.id if hasattr(complaint.resident_id, "ref") else str(complaint.resident_id)
        if str(owner_id) != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if complaint.status != ComplaintStatus.open:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only open complaints can be edited")

    return await update_complaint(complaint, payload)


@router.delete("/{complaint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_complaint(
    complaint_id: str,
    _admin: Annotated[User, Depends(get_current_admin)],
) -> None:
    """Admin-only: permanently delete a complaint."""
    complaint = await get_complaint(complaint_id)
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")
    await delete_complaint(complaint)
