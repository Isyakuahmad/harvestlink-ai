from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_user
from app.models import AuditLog, BuyerRequirement, MatchCandidate, ProduceListing, User, WorkflowRun
from app.procurement_models import BuyerInterest, ProcurementTransaction, TransactionEvent

router = APIRouter(prefix="/api/v1", tags=["procurement"])
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


class InterestCreate(BaseModel):
    message: str = Field(default="", max_length=1000)


class InterestResponse(BaseModel):
    decision: str = Field(pattern="^(accept|decline|clarification)$")
    message: str = Field(default="", max_length=1000)


class TermsProposal(BaseModel):
    quantity: float = Field(gt=0, le=10_000_000)
    unit: str = Field(pattern="^(kg|tonne)$")
    price_per_unit: float = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    delivery_location: str = Field(min_length=2, max_length=180)
    delivery_date: date
    notes: str = Field(default="", max_length=1000)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


def _interest_view(item: BuyerInterest) -> dict:
    return {
        "id": item.id,
        "match_candidate_id": item.match_candidate_id,
        "buyer_user_id": item.buyer_user_id,
        "farmer_user_id": item.farmer_user_id,
        "status": item.status,
        "buyer_message": item.buyer_message,
        "farmer_message": item.farmer_message,
        "created_at": item.created_at,
        "responded_at": item.responded_at,
    }


def _transaction_view(item: ProcurementTransaction, user_id: int) -> dict:
    return {
        "id": item.id,
        "status": item.status,
        "role": "buyer" if item.buyer_user_id == user_id else "farmer",
        "terms": item.agreed_terms_json or item.proposed_terms_json,
        "created_at": item.created_at,
        "confirmed_at": item.confirmed_at,
        "delivered_at": item.delivered_at,
    }


@router.get("/marketplace/matches")
def list_buyer_matches(db: DatabaseSession, user: CurrentUser):
    if user.role != "buyer" or user.verification_status != "verified":
        raise HTTPException(status_code=403, detail="A verified buyer account is required")
    rows = (
        db.query(MatchCandidate, BuyerRequirement, ProduceListing, User)
        .join(BuyerRequirement, MatchCandidate.buyer_requirement_id == BuyerRequirement.id)
        .join(WorkflowRun, MatchCandidate.workflow_run_id == WorkflowRun.id)
        .join(ProduceListing, WorkflowRun.listing_id == ProduceListing.id)
        .join(User, ProduceListing.farmer_user_id == User.id)
        .filter(
            BuyerRequirement.buyer_user_id == user.id,
            BuyerRequirement.is_active.is_(True),
            MatchCandidate.eligible.is_(True),
            ProduceListing.status == "approved",
            User.verification_status == "verified",
        )
        .order_by(MatchCandidate.score.desc(), MatchCandidate.created_at.desc())
        .all()
    )
    output = []
    for match, requirement, listing, farmer in rows:
        output.append({
            "match_id": match.id,
            "requirement_id": requirement.id,
            "listing_id": listing.id,
            "crop_name": listing.crop_name,
            "quantity": listing.quantity,
            "unit": listing.unit,
            "quality": listing.quality_description,
            "location": listing.location,
            "available_on": listing.available_on,
            "asking_price": listing.asking_price,
            "currency": listing.currency,
            "match_score": match.score,
            "reasons": match.reasons_json,
            "farmer_name": farmer.full_name,
        })
    return output


@router.post("/marketplace/matches/{match_id}/interest", status_code=201)
def express_interest(match_id: int, payload: InterestCreate, db: DatabaseSession, user: CurrentUser):
    if user.role != "buyer" or user.verification_status != "verified":
        raise HTTPException(status_code=403, detail="A verified buyer account is required")
    row = (
        db.query(MatchCandidate, BuyerRequirement, ProduceListing, User)
        .join(BuyerRequirement, MatchCandidate.buyer_requirement_id == BuyerRequirement.id)
        .join(WorkflowRun, MatchCandidate.workflow_run_id == WorkflowRun.id)
        .join(ProduceListing, WorkflowRun.listing_id == ProduceListing.id)
        .join(User, ProduceListing.farmer_user_id == User.id)
        .filter(
            MatchCandidate.id == match_id,
            BuyerRequirement.buyer_user_id == user.id,
            BuyerRequirement.is_active.is_(True),
            MatchCandidate.eligible.is_(True),
            ProduceListing.status == "approved",
            User.verification_status == "verified",
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Eligible match not found")
    match, requirement, listing, farmer = row
    existing = db.query(BuyerInterest).filter(BuyerInterest.match_candidate_id == match.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Interest has already been submitted for this match")
    interest = BuyerInterest(
        match_candidate_id=match.id,
        buyer_user_id=user.id,
        farmer_user_id=farmer.id,
        buyer_message=payload.message.strip(),
    )
    db.add(interest)
    db.flush()
    db.add(AuditLog(
        actor_user_id=user.id, action="buyer.interest_submitted",
        subject_type="buyer_interest", subject_id=interest.id,
        details_json={"match_id": match.id, "listing_id": listing.id, "requirement_id": requirement.id},
    ))
    db.commit()
    db.refresh(interest)
    return _interest_view(interest)


@router.get("/interests")
def list_interests(db: DatabaseSession, user: CurrentUser):
    if user.role not in {"buyer", "farmer"}:
        raise HTTPException(status_code=403, detail="Marketplace participant access required")
    query = db.query(BuyerInterest)
    query = query.filter(
        BuyerInterest.buyer_user_id == user.id if user.role == "buyer"
        else BuyerInterest.farmer_user_id == user.id
    )
    return [_interest_view(item) for item in query.order_by(BuyerInterest.created_at.desc()).all()]


@router.post("/interests/{interest_id}/response")
def respond_to_interest(
    interest_id: int, payload: InterestResponse, db: DatabaseSession, user: CurrentUser
):
    if user.role != "farmer":
        raise HTTPException(status_code=403, detail="Only the farmer can respond to buyer interest")
    interest = (
        db.query(BuyerInterest).filter(
            BuyerInterest.id == interest_id, BuyerInterest.farmer_user_id == user.id
        ).with_for_update().first()
    )
    if interest is None:
        raise HTTPException(status_code=404, detail="Interest not found")
    if interest.status != "pending":
        raise HTTPException(status_code=409, detail="Interest has already been answered")
    interest.status = {
        "accept": "accepted", "decline": "declined", "clarification": "clarification_requested"
    }[payload.decision]
    interest.farmer_message = payload.message.strip()
    interest.responded_at = datetime.now(UTC)
    db.add(AuditLog(
        actor_user_id=user.id, action=f"farmer.interest_{payload.decision}",
        subject_type="buyer_interest", subject_id=interest.id,
        details_json={"message": interest.farmer_message},
    ))
    db.commit()
    db.refresh(interest)
    return _interest_view(interest)


@router.post("/interests/{interest_id}/terms", status_code=201)
def propose_transaction_terms(
    interest_id: int, payload: TermsProposal, db: DatabaseSession, user: CurrentUser
):
    if user.role != "buyer" or user.verification_status != "verified":
        raise HTTPException(status_code=403, detail="A verified buyer account is required")
    interest = db.query(BuyerInterest).filter(
        BuyerInterest.id == interest_id, BuyerInterest.buyer_user_id == user.id
    ).first()
    if interest is None:
        raise HTTPException(status_code=404, detail="Accepted interest not found")
    if interest.status != "accepted":
        raise HTTPException(status_code=409, detail="Farmer must accept the interest first")
    existing = db.query(ProcurementTransaction).filter(
        ProcurementTransaction.interest_id == interest.id
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Terms have already been proposed")
    match_row = (
        db.query(MatchCandidate, WorkflowRun, ProduceListing)
        .join(WorkflowRun, MatchCandidate.workflow_run_id == WorkflowRun.id)
        .join(ProduceListing, WorkflowRun.listing_id == ProduceListing.id)
        .filter(MatchCandidate.id == interest.match_candidate_id)
        .first()
    )
    if match_row is None:
        raise HTTPException(status_code=404, detail="Matched produce listing not found")
    _, _, listing = match_row
    proposed_base_quantity = payload.quantity * (1000 if payload.unit == "tonne" else 1)
    listed_base_quantity = listing.quantity * (1000 if listing.unit == "tonne" else 1)
    if proposed_base_quantity > listed_base_quantity:
        raise HTTPException(status_code=422, detail="Agreed quantity cannot exceed the listed quantity")
    terms = payload.model_dump(mode="json")
    transaction = ProcurementTransaction(
        interest_id=interest.id, buyer_user_id=user.id, farmer_user_id=interest.farmer_user_id,
        listing_id=listing.id, status="terms_proposed", proposed_terms_json=terms,
    )
    db.add(transaction)
    db.flush()
    db.add(TransactionEvent(
        transaction_id=transaction.id, actor_user_id=user.id,
        event_type="terms_proposed", details_json=terms,
    ))
    db.add(AuditLog(
        actor_user_id=user.id, action="transaction.terms_proposed",
        subject_type="procurement_transaction", subject_id=transaction.id, details_json=terms,
    ))
    db.commit()
    db.refresh(transaction)
    return _transaction_view(transaction, user.id)


@router.post("/transactions/{transaction_id}/confirm")
def confirm_transaction(transaction_id: int, db: DatabaseSession, user: CurrentUser):
    if user.role != "farmer":
        raise HTTPException(status_code=403, detail="Only the farmer can confirm proposed terms")
    transaction = db.query(ProcurementTransaction).filter(
        ProcurementTransaction.id == transaction_id,
        ProcurementTransaction.farmer_user_id == user.id,
    ).with_for_update().first()
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if transaction.status != "terms_proposed":
        raise HTTPException(status_code=409, detail="Transaction terms are not awaiting confirmation")
    transaction.agreed_terms_json = dict(transaction.proposed_terms_json)
    transaction.status = "confirmed"
    transaction.confirmed_at = datetime.now(UTC)
    db.add(TransactionEvent(
        transaction_id=transaction.id, actor_user_id=user.id,
        event_type="terms_confirmed", details_json={"terms": transaction.agreed_terms_json},
    ))
    db.add(AuditLog(
        actor_user_id=user.id, action="transaction.terms_confirmed",
        subject_type="procurement_transaction", subject_id=transaction.id,
        details_json={"terms": transaction.agreed_terms_json},
    ))
    db.commit()
    db.refresh(transaction)
    return _transaction_view(transaction, user.id)


@router.get("/transactions")
def list_transactions(db: DatabaseSession, user: CurrentUser):
    if user.role not in {"buyer", "farmer"}:
        raise HTTPException(status_code=403, detail="Marketplace participant access required")
    query = db.query(ProcurementTransaction).filter(
        ProcurementTransaction.buyer_user_id == user.id
        if user.role == "buyer" else ProcurementTransaction.farmer_user_id == user.id
    )
    return [_transaction_view(item, user.id) for item in query.order_by(
        ProcurementTransaction.created_at.desc()
    ).all()]


@router.get("/transactions/{transaction_id}")
def get_transaction(transaction_id: int, db: DatabaseSession, user: CurrentUser):
    transaction = db.query(ProcurementTransaction).filter(
        ProcurementTransaction.id == transaction_id,
        (ProcurementTransaction.buyer_user_id == user.id)
        | (ProcurementTransaction.farmer_user_id == user.id),
    ).first()
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    events = db.query(TransactionEvent).filter(
        TransactionEvent.transaction_id == transaction.id
    ).order_by(TransactionEvent.created_at.asc()).all()
    result = _transaction_view(transaction, user.id)
    result["events"] = [
        {"event_type": event.event_type, "details": event.details_json, "created_at": event.created_at}
        for event in events
    ]
    return result


@router.post("/transactions/{transaction_id}/delivery")
def record_delivery(transaction_id: int, payload: InterestCreate, db: DatabaseSession, user: CurrentUser):
    transaction = db.query(ProcurementTransaction).filter(
        ProcurementTransaction.id == transaction_id,
        (ProcurementTransaction.buyer_user_id == user.id)
        | (ProcurementTransaction.farmer_user_id == user.id),
    ).with_for_update().first()
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if transaction.status != "confirmed":
        raise HTTPException(status_code=409, detail="Only confirmed transactions can be marked delivered")
    transaction.status = "delivered"
    transaction.delivered_at = datetime.now(UTC)
    details = {"evidence_note": payload.message.strip()}
    db.add(TransactionEvent(
        transaction_id=transaction.id, actor_user_id=user.id,
        event_type="delivery_recorded", details_json=details,
    ))
    db.add(AuditLog(
        actor_user_id=user.id, action="transaction.delivery_recorded",
        subject_type="procurement_transaction", subject_id=transaction.id, details_json=details,
    ))
    db.commit()
    db.refresh(transaction)
    return _transaction_view(transaction, user.id)
