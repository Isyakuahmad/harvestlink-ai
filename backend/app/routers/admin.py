from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_user
from app.models import AuditLog, BuyerProfile, ProduceListing, User, VerificationCase
from app.schemas import VerificationDecision

router = APIRouter(prefix="/api/v1/admin", tags=["administration"])
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


@router.get("/verification-cases")
def list_verification_cases(
    db: DatabaseSession,
    admin: AdminUser,
    status: str = Query(default="pending", pattern="^(pending|approved|rejected|all)$"),
):
    query = db.query(VerificationCase)
    if status != "all":
        query = query.filter(VerificationCase.status == status)
    cases = query.order_by(VerificationCase.created_at.asc()).all()
    output = []
    for case in cases:
        submitted_by = db.query(User).filter(User.id == case.submitted_by_user_id).first()
        subject = None
        if case.subject_type == "user":
            subject = db.query(User).filter(User.id == case.subject_id).first()
            buyer_profile = (
                db.query(BuyerProfile).filter(BuyerProfile.user_id == case.subject_id).first()
            )
        elif case.subject_type == "listing":
            subject = db.query(ProduceListing).filter(ProduceListing.id == case.subject_id).first()
        output.append({
            "id": case.id,
            "subject_type": case.subject_type,
            "subject_id": case.subject_id,
            "status": case.status,
            "submitted_by": submitted_by.email if submitted_by else None,
            "subject": (
                {"email": subject.email, "full_name": subject.full_name,
                 "role": subject.role, "verification_status": subject.verification_status,
                 "buyer_profile": (
                     {"organization_name": buyer_profile.organization_name,
                      "buyer_type": buyer_profile.buyer_type, "phone": buyer_profile.phone,
                      "location": buyer_profile.location}
                     if case.subject_type == "user" and buyer_profile else None
                 )}
                if case.subject_type == "user" and subject else
                {"crop_name": subject.crop_name, "quantity": subject.quantity,
                 "unit": subject.unit, "location": subject.location, "status": subject.status}
                if case.subject_type == "listing" and subject else None
            ),
            "review_reason": case.review_reason,
            "created_at": case.created_at,
        })
    return output


@router.post("/verification-cases/{case_id}/decision")
def decide_verification_case(
    case_id: int,
    payload: VerificationDecision,
    db: DatabaseSession,
    admin: AdminUser,
):
    case = db.query(VerificationCase).filter(VerificationCase.id == case_id).with_for_update().first()
    if case is None:
        raise HTTPException(status_code=404, detail="Verification case not found")
    if case.status != "pending":
        raise HTTPException(status_code=409, detail="This verification case has already been reviewed")

    approved = payload.decision == "approve"
    if case.subject_type == "user":
        subject = db.query(User).filter(User.id == case.subject_id).with_for_update().first()
        if subject is None:
            raise HTTPException(status_code=404, detail="Account for this case no longer exists")
        subject.verification_status = "verified" if approved else "rejected"
    elif case.subject_type == "listing":
        listing = db.query(ProduceListing).filter(ProduceListing.id == case.subject_id).with_for_update().first()
        if listing is None:
            raise HTTPException(status_code=404, detail="Listing for this case no longer exists")
        farmer = db.query(User).filter(User.id == listing.farmer_user_id).first()
        if approved and (farmer is None or farmer.verification_status != "verified"):
            raise HTTPException(
                status_code=409,
                detail="Approve the farmer identity before approving this listing",
            )
        listing.status = "approved" if approved else "rejected"
    else:
        raise HTTPException(status_code=422, detail="Unsupported verification subject")

    now = datetime.now(UTC)
    case.status = "approved" if approved else "rejected"
    case.review_reason = payload.reason.strip()
    case.reviewed_by_user_id = admin.id
    case.reviewed_at = now
    db.add(AuditLog(
        actor_user_id=admin.id,
        action=f"verification.{payload.decision}",
        subject_type=case.subject_type,
        subject_id=case.subject_id,
        details_json={"case_id": case.id, "reason": payload.reason.strip()},
    ))
    db.commit()
    return {
        "case_id": case.id,
        "subject_type": case.subject_type,
        "subject_id": case.subject_id,
        "status": case.status,
        "review_reason": case.review_reason,
        "reviewed_at": case.reviewed_at,
    }

 
@router.get("/audit-logs")
def list_audit_logs(
    db: DatabaseSession,
    admin: AdminUser,
    limit: int = Query(default=100, ge=1, le=500),
):
    entries = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": entry.id,
            "actor_user_id": entry.actor_user_id,
            "action": entry.action,
            "subject_type": entry.subject_type,
            "subject_id": entry.subject_id,
            "details": entry.details_json,
            "created_at": entry.created_at,
        }
        for entry in entries
    ]
