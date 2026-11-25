"""Evidence-backed market price submissions, review and summaries."""
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.agents.market_intelligence import build_market_summary, normalize_commodity
from app.db import get_db
from app.dependencies import get_current_user
from app.market_intelligence_models import MarketPriceObservation
from app.models import User

router = APIRouter(prefix="/api/v1/market-intelligence", tags=["market-intelligence"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


class MarketObservationCreate(BaseModel):
    commodity: str = Field(min_length=2, max_length=100)
    market_name: str = Field(min_length=2, max_length=160)
    state: str = Field(min_length=2, max_length=100)
    observed_on: date
    unit: str = Field(pattern="^(kg|tonne|bag|crate|litre)$")
    currency: str = Field(default="NGN", min_length=3, max_length=3)
    min_price: float = Field(gt=0, le=1_000_000_000)
    max_price: float = Field(gt=0, le=1_000_000_000)
    modal_price: float = Field(gt=0, le=1_000_000_000)
    quality_grade: str = Field(default="", max_length=100)
    source_name: str = Field(min_length=2, max_length=180)
    source_url: str | None = Field(default=None, max_length=1000)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("https://", "http://")):
            raise ValueError("source_url must be an http(s) URL")
        return value


def _observation_view(row: MarketPriceObservation) -> dict:
    return {
        "id": row.id, "commodity": row.commodity, "market_name": row.market_name,
        "state": row.state, "observed_on": row.observed_on.isoformat(),
        "unit": row.unit, "currency": row.currency, "min_price": row.min_price,
        "max_price": row.max_price, "modal_price": row.modal_price,
        "quality_grade": row.quality_grade, "source_name": row.source_name,
        "source_url": row.source_url, "verification_status": row.verification_status,
    }


@router.post("/observations", status_code=201)
def submit_observation(payload: MarketObservationCreate, db: Db, user: CurrentUser):
    if not user.is_active or user.verification_status != "verified":
        raise HTTPException(status_code=403, detail="A verified, active account is required")
    if payload.observed_on > date.today():
        raise HTTPException(status_code=422, detail="Observation date cannot be in the future")
    if payload.min_price > payload.modal_price or payload.modal_price > payload.max_price:
        raise HTTPException(status_code=422, detail="Prices must satisfy min_price <= modal_price <= max_price")
    row = MarketPriceObservation(
        **payload.model_dump(exclude={"commodity", "market_name", "state", "quality_grade", "source_name"}),
        commodity=normalize_commodity(payload.commodity),
        market_name=payload.market_name.strip(),
        state=payload.state.strip(),
        quality_grade=payload.quality_grade.strip(),
        source_name=payload.source_name.strip(),
        source_type="user_report",
        verification_status="pending_review",
        submitted_by_user_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _observation_view(row)


@router.get("/observations")
def list_observations(
    db: Db, user: CurrentUser,
    commodity: str = Query(min_length=2, max_length=100),
    state: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
):
    if not user.is_active or user.verification_status != "verified":
        raise HTTPException(status_code=403, detail="A verified, active account is required")
    query = db.query(MarketPriceObservation).filter(
        MarketPriceObservation.commodity == normalize_commodity(commodity),
        MarketPriceObservation.verification_status == "approved",
    )
    if state:
        query = query.filter(MarketPriceObservation.state.ilike(state.strip()))
    rows = query.order_by(MarketPriceObservation.observed_on.desc()).limit(limit).all()
    return [_observation_view(row) for row in rows]


@router.get("/summary")
def market_summary(
    db: Db, user: CurrentUser,
    commodity: str = Query(min_length=2, max_length=100),
    state: str | None = Query(default=None, max_length=100),
    market_name: str | None = Query(default=None, max_length=160),
    days: int = Query(default=30, ge=1, le=365),
):
    if not user.is_active or user.verification_status != "verified":
        raise HTTPException(status_code=403, detail="A verified, active account is required")
    cutoff = date.today().fromordinal(date.today().toordinal() - days + 1)
    query = db.query(MarketPriceObservation).filter(
        MarketPriceObservation.commodity == normalize_commodity(commodity),
        MarketPriceObservation.verification_status == "approved",
        MarketPriceObservation.observed_on >= cutoff,
    )
    if state:
        query = query.filter(MarketPriceObservation.state.ilike(state.strip()))
    if market_name:
        query = query.filter(MarketPriceObservation.market_name.ilike(market_name.strip()))
    rows = query.order_by(MarketPriceObservation.observed_on.desc()).all()
    try:
        summary = build_market_summary(rows)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"commodity": normalize_commodity(commodity), "state": state,
            "market_name": market_name, "period_days": days, **summary}


@router.post("/observations/{observation_id}/review")
def review_observation(observation_id: int, decision: str, db: Db, user: CurrentUser):
    if user.role != "admin" or not user.is_active:
        raise HTTPException(status_code=403, detail="Administrator access required")
    if decision not in {"approve", "reject"}:
        raise HTTPException(status_code=422, detail="Decision must be approve or reject")
    row = db.query(MarketPriceObservation).filter(
        MarketPriceObservation.id == observation_id
    ).with_for_update().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Market observation not found")
    if row.verification_status != "pending_review":
        raise HTTPException(status_code=409, detail="Observation has already been reviewed")
    row.verification_status = "approved" if decision == "approve" else "rejected"
    row.reviewed_by_user_id = user.id
    row.reviewed_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return _observation_view(row)
