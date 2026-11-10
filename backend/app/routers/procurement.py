from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_user
from app.models import AuditLog, BuyerRequirement, MatchCandidate, ProduceListing, User, WorkflowRun
from app.procurement_models import (
    BuyerInterest,
    LogisticsProviderProfile,
    LogisticsQuote,
    LogisticsQuoteRequest,
    ProcurementTransaction,
    TransactionEvent,
)

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


class LogisticsRequestCreate(BaseModel):
    destination: str = Field(min_length=2, max_length=180)
    pickup_date: date
    cargo_description: str = Field(min_length=3, max_length=1000)


class LogisticsQuoteCreate(BaseModel):
    amount: float = Field(gt=0, le=1_000_000_000)
    currency: str = Field(min_length=3, max_length=3)
    estimated_days: int = Field(gt=0, le=365)
    notes: str = Field(default="", max_length=1000)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class TransactionIssue(BaseModel):
    description: str = Field(min_length=5, max_length=2000)


@router.post("/transactions/{transaction_id}/logistics-requests", status_code=201)
def create_logistics_request(
    transaction_id: int, payload: LogisticsRequestCreate, db: DatabaseSession, user: CurrentUser
):
    transaction = db.query(ProcurementTransaction).filter(
        ProcurementTransaction.id == transaction_id,
        (ProcurementTransaction.buyer_user_id == user.id)
        | (ProcurementTransaction.farmer_user_id == user.id),
    ).first()
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if transaction.status != "confirmed":
        raise HTTPException(status_code=409, detail="Only confirmed transactions can request logistics")
    listing = db.query(ProduceListing).filter(ProduceListing.id == transaction.listing_id).first()
    request = LogisticsQuoteRequest(
        transaction_id=transaction.id,
        requested_by_user_id=user.id,
        origin=listing.location,
        destination=payload.destination.strip(),
        pickup_date=datetime.combine(payload.pickup_date, datetime.min.time(), tzinfo=UTC),
        cargo_description=payload.cargo_description.strip(),
    )
    db.add(request)
    db.flush()
    db.add(TransactionEvent(
        transaction_id=transaction.id, actor_user_id=user.id,
        event_type="logistics_quote_requested",
        details_json={"request_id": request.id, "destination": request.destination},
    ))
    db.commit()
    db.refresh(request)
    return {
        "id": request.id, "transaction_id": request.transaction_id,
        "origin": request.origin, "destination": request.destination,
        "pickup_date": request.pickup_date, "cargo_description": request.cargo_description,
        "status": request.status,
    }


@router.get("/logistics/requests")
def list_logistics_requests(db: DatabaseSession, user: CurrentUser):
    if user.role != "logistics_provider" or user.verification_status != "verified":
        raise HTTPException(status_code=403, detail="A verified logistics provider account is required")
    requests = db.query(LogisticsQuoteRequest).filter(
        LogisticsQuoteRequest.status == "open"
    ).order_by(LogisticsQuoteRequest.created_at.desc()).all()
    return [{
        "id": item.id, "origin": item.origin, "destination": item.destination,
        "pickup_date": item.pickup_date, "cargo_description": item.cargo_description,
    } for item in requests]


@router.post("/logistics/requests/{request_id}/quotes", status_code=201)
def submit_logistics_quote(
    request_id: int, payload: LogisticsQuoteCreate, db: DatabaseSession, user: CurrentUser
):
    if user.role != "logistics_provider" or user.verification_status != "verified":
        raise HTTPException(status_code=403, detail="A verified logistics provider account is required")
    provider = db.query(LogisticsProviderProfile).filter(
        LogisticsProviderProfile.user_id == user.id
    ).first()
    if provider is None:
        raise HTTPException(status_code=403, detail="Logistics provider profile is missing")
    request = db.query(LogisticsQuoteRequest).filter(
        LogisticsQuoteRequest.id == request_id, LogisticsQuoteRequest.status == "open"
    ).first()
    if request is None:
        raise HTTPException(status_code=404, detail="Open logistics request not found")
    existing = db.query(LogisticsQuote).filter(
        LogisticsQuote.request_id == request.id,
        LogisticsQuote.provider_user_id == user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="You have already quoted this request")
    quote = LogisticsQuote(
        request_id=request.id, provider_user_id=user.id, amount=payload.amount,
        currency=payload.currency, estimated_days=payload.estimated_days,
        notes=payload.notes.strip(),
    )
    db.add(quote)
    db.commit()
    db.refresh(quote)
    return {
        "id": quote.id, "request_id": quote.request_id, "amount": quote.amount,
        "currency": quote.currency, "estimated_days": quote.estimated_days,
        "notes": quote.notes, "status": quote.status,
    }


@router.get("/transactions/{transaction_id}/logistics-quotes")
def list_transaction_quotes(transaction_id: int, db: DatabaseSession, user: CurrentUser):
    transaction = db.query(ProcurementTransaction).filter(
        ProcurementTransaction.id == transaction_id,
        (ProcurementTransaction.buyer_user_id == user.id)
        | (ProcurementTransaction.farmer_user_id == user.id),
    ).first()
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    requests = db.query(LogisticsQuoteRequest).filter(
        LogisticsQuoteRequest.transaction_id == transaction.id
    ).all()
    result = []
    for request in requests:
        for quote in db.query(LogisticsQuote).filter(LogisticsQuote.request_id == request.id).all():
            result.append({
                "id": quote.id, "request_id": request.id,
                "provider_user_id": quote.provider_user_id, "amount": quote.amount,
                "currency": quote.currency, "estimated_days": quote.estimated_days,
                "notes": quote.notes, "status": quote.status,
                "buyer_approved": quote.buyer_approved_at is not None,
                "farmer_approved": quote.farmer_approved_at is not None,
            })
    return result


@router.post("/logistics/quotes/{quote_id}/approve")
def approve_logistics_quote(quote_id: int, db: DatabaseSession, user: CurrentUser):
    quote = db.query(LogisticsQuote).filter(LogisticsQuote.id == quote_id).first()
    if quote is None:
        raise HTTPException(status_code=404, detail="Logistics quote not found")
    request = db.query(LogisticsQuoteRequest).filter(
        LogisticsQuoteRequest.id == quote.request_id
    ).first()
    transaction = db.query(ProcurementTransaction).filter(
        ProcurementTransaction.id == request.transaction_id,
        (ProcurementTransaction.buyer_user_id == user.id)
        | (ProcurementTransaction.farmer_user_id == user.id),
    ).with_for_update().first()
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if quote.status not in {"submitted", "awaiting_provider"}:
        raise HTTPException(status_code=409, detail="Quote is no longer awaiting approvals")
    now = datetime.now(UTC)
    if user.id == transaction.buyer_user_id:
        if quote.buyer_approved_at is not None:
            raise HTTPException(status_code=409, detail="Buyer approval already recorded")
        quote.buyer_approved_at = now
    else:
        if quote.farmer_approved_at is not None:
            raise HTTPException(status_code=409, detail="Farmer approval already recorded")
        quote.farmer_approved_at = now
    if quote.buyer_approved_at and quote.farmer_approved_at:
        quote.status = "awaiting_provider"
    db.add(TransactionEvent(
        transaction_id=transaction.id, actor_user_id=user.id,
        event_type="logistics_quote_party_approved",
        details_json={"quote_id": quote.id, "status": quote.status},
    ))
    db.commit()
    return {
        "quote_id": quote.id, "status": quote.status,
        "buyer_approved": quote.buyer_approved_at is not None,
        "farmer_approved": quote.farmer_approved_at is not None,
    }


@router.post("/logistics/quotes/{quote_id}/provider-confirm")
def provider_confirm_logistics_quote(quote_id: int, db: DatabaseSession, user: CurrentUser):
    if user.role != "logistics_provider" or user.verification_status != "verified":
        raise HTTPException(status_code=403, detail="A verified logistics provider account is required")
    quote = db.query(LogisticsQuote).filter(
        LogisticsQuote.id == quote_id, LogisticsQuote.provider_user_id == user.id
    ).with_for_update().first()
    if quote is None:
        raise HTTPException(status_code=404, detail="Logistics quote not found")
    if quote.status != "awaiting_provider" or not quote.buyer_approved_at or not quote.farmer_approved_at:
        raise HTTPException(status_code=409, detail="Both buyer and farmer must approve before provider confirmation")
    quote.status = "booked"
    quote.provider_confirmed_at = datetime.now(UTC)
    request = db.query(LogisticsQuoteRequest).filter(
        LogisticsQuoteRequest.id == quote.request_id
    ).first()
    db.add(TransactionEvent(
        transaction_id=request.transaction_id, actor_user_id=user.id,
        event_type="logistics_booking_confirmed", details_json={"quote_id": quote.id},
    ))
    db.commit()
    return {"quote_id": quote.id, "status": quote.status, "provider_confirmed_at": quote.provider_confirmed_at}


@router.post("/transactions/{transaction_id}/issue")
def report_transaction_issue(
    transaction_id: int, payload: TransactionIssue, db: DatabaseSession, user: CurrentUser
):
    transaction = db.query(ProcurementTransaction).filter(
        ProcurementTransaction.id == transaction_id,
        (ProcurementTransaction.buyer_user_id == user.id)
        | (ProcurementTransaction.farmer_user_id == user.id),
    ).with_for_update().first()
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if transaction.status not in {"confirmed", "delivered"}:
        raise HTTPException(status_code=409, detail="Issue can only be reported on an active transaction")
    transaction.status = "issue_reported"
    db.add(TransactionEvent(
        transaction_id=transaction.id, actor_user_id=user.id,
        event_type="issue_reported", details_json={"description": payload.description.strip()},
    ))
    db.add(AuditLog(
        actor_user_id=user.id, action="transaction.issue_reported",
        subject_type="procurement_transaction", subject_id=transaction.id,
        details_json={"description": payload.description.strip()},
    ))
    db.commit()
    return {"transaction_id": transaction.id, "status": transaction.status}
