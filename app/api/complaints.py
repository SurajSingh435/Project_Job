"""
app/api/complaints.py — Complaint endpoints (Phase 3).

Route map
-------------------------------------------------------------
POST   /api/v1/complaints              resident  create
GET    /api/v1/my-complaints           resident  list own
GET    /api/v1/admin/complaints        admin     list all (filterable)
PATCH  /api/v1/admin/complaints/{id}/status  admin  update status
DELETE /api/v1/admin/complaints/{id}   admin     hard delete
GET    /api/v1/complaints/{id}         any auth  fetch single (ownership enforced)
"""
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user, require_admin
from app.models.complaint import Complaint, ComplaintStatus
from app.models.user import User, UserRole
from app.schemas.complaint import (
    NLSearchQuery,
    ComplaintCreate,
    ComplaintListRead,
    ComplaintRead,
    StatusUpdate,
)
from app.services.complaint_service import (
    create_complaint,
    delete_complaint,
    get_complaint_by_id,
    list_all_complaints,
    list_my_complaints,
    update_status,
)

router = APIRouter(tags=["Complaints"])


# ---------------------------------------------------------------------------
# Resident routes
# ---------------------------------------------------------------------------

@router.post("/complaints", response_model=ComplaintRead, status_code=status.HTTP_201_CREATED)
async def submit_complaint(
    payload: ComplaintCreate,
    current_user: Annotated[User, Depends(get_current_user)],
) -> Complaint:
    """
    **Resident** — file a new complaint.

    Requires an active session (any role).  
    Returns the created complaint with HTTP 201.
    """
    return await create_complaint(payload, current_user)


@router.get("/my-complaints", response_model=List[ComplaintListRead])
async def get_my_complaints(
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = Query(default=0, ge=0, description="Pagination offset"),
    limit: int = Query(default=20, ge=1, le=100, description="Max results to return"),
) -> List[Complaint]:
    """
    **Resident** — list only the complaints filed by the logged-in user.

    Results are sorted newest-first.  
    Admins calling this endpoint will see only complaints they personally filed
    (use `/admin/complaints` for the global view).
    """
    return await list_my_complaints(
        resident_id=str(current_user.id),
        skip=skip,
        limit=limit,
    )


@router.get("/complaints/{complaint_id}", response_model=ComplaintRead)
async def get_complaint_detail(
    complaint_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> Complaint:
    """
    Fetch a single complaint by ID.

    - **Residents** may only view complaints they filed (403 otherwise).  
    - **Admins** may view any complaint.
    """
    complaint = await get_complaint_by_id(complaint_id)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{complaint_id}' not found",
        )

    if current_user.role != UserRole.admin:
        _assert_owner(complaint, current_user)

    return complaint


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------

@router.get("/admin/complaints", response_model=List[ComplaintListRead])
async def admin_list_complaints(
    _admin: Annotated[User, Depends(require_admin)],
    complaint_status: Optional[ComplaintStatus] = Query(
        default=None,
        alias="status",
        description="Filter by status: open | in_progress | resolved",
    ),
    category: Optional[str] = Query(
        default=None,
        description="Filter by category (case-insensitive exact match)",
    ),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> List[Complaint]:
    """
    **Admin** — list ALL complaints across all residents.

    Optional query filters:  
    - `?status=open` / `in_progress` / `resolved`  
    - `?category=road`

    Results are sorted newest-first.
    """
    return await list_all_complaints(
        status=complaint_status,
        category=category,
        skip=skip,
        limit=limit,
    )


@router.patch(
    "/admin/complaints/{complaint_id}/status",
    response_model=ComplaintRead,
)
async def admin_update_status(
    complaint_id: str,
    payload: StatusUpdate,
    _admin: Annotated[User, Depends(require_admin)],
) -> Complaint:
    """
    **Admin** — update the status of a complaint.

    Accepted values: `open`, `in_progress`, `resolved`.  
    Returns 404 if the complaint does not exist.
    """
    complaint = await get_complaint_by_id(complaint_id)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{complaint_id}' not found",
        )
    return await update_status(complaint, payload.status)


@router.delete(
    "/admin/complaints/{complaint_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def admin_delete_complaint(
    complaint_id: str,
    _admin: Annotated[User, Depends(require_admin)],
) -> None:
    """
    **Admin** — permanently delete a complaint. Returns 204.
    """
    complaint = await get_complaint_by_id(complaint_id)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{complaint_id}' not found",
        )
    await delete_complaint(complaint)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _assert_owner(complaint: Complaint, user: User) -> None:
    """
    Raise 403 if *user* is not the owner of *complaint*.

    Works whether Beanie has fetched the Link (User object) or left it
    as a raw DBRef dict.
    """
    owner_id = _resolve_resident_id(complaint)
    if owner_id != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this complaint",
        )


def _resolve_resident_id(complaint: Complaint) -> str:
    """Extract the owner ObjectId string from a Complaint regardless of fetch state."""
    ref = complaint.resident_id
    # Fetched Link ? User document
    if isinstance(ref, dict):
        return str(ref.get("$id", ""))
    # Beanie Link wrapper (unfetched)
    if hasattr(ref, "ref"):
        return str(ref.ref.id)
    # Already a User document
    if hasattr(ref, "id"):
        return str(ref.id)
    return str(ref)

@router.post("/admin/search", response_model=List[ComplaintListRead])
async def admin_nl_search(
    payload: NLSearchQuery,
    _admin: Annotated[User, Depends(require_admin)]
) -> List[Complaint]:
    """
    **Admin** - search complaints using natural language.
    
    Accepts queries like "show open electrical complaints from last 7 days".
    Uses an LLM to extract structured filters securely.
    """
    from app.services.ai_service import parse_nl_search
    from app.services.complaint_service import search_complaints_by_filter
    
    # 1. Ask LLM to parse natural language into structured filters
    parsed_filters = await parse_nl_search(payload.query)
    
    # 2. Build and execute MongoDB query using strict whitelists
    return await search_complaints_by_filter(parsed_filters)
