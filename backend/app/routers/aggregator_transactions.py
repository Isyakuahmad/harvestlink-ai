"""Offer, accept and reserve aggregator-owned stock."""
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.aggregator_transaction_models import (
    AggregatorStockDeal,
    AggregatorStockDealEvent,
    AggregatorStockOffer,
)
from app.db import get_db
from app.dependencies import get_current_user
from app.models import AuditLog, BuyerProfile, User
from app.supply_chain_models import AggregatorStockLot

router = APIRouter(prefix="/api/v1/aggregator", tags=["aggregator-transactions"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


class StockOfferCreate(BaseModel):
    quantity: float = Field(gt=0)
    unit: str = Field(pattern="^(kg|tonne)$")
    price_per_unit: float = Field(gt=0, le=1_000_000_000)
    currency: str = Field(min_length=3, max_length=3)
    message: str = Field(default="", max_length=1000)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class OfferDecision(BaseModel):
    decision: str = Field(pattern="^(accept|reject)$")
    message: str = Field(default="", max_length=1000)


def _buyer_type(db: Session, user_id: int) -> str | None:
    profile = db.query(BuyerProfile).filter(BuyerProfile.user_id == user_id).first()
    return profile.buyer_type.casefold() if profile else None


def _offer_view(offer: AggregatorStockOffer) -> dict:
    return {"id": offer.id, "stock_lot_id": offer.stock_lot_id,
            "aggregator_user_id": offer.aggregator_user_id, "buyer_user_id": offer.buyer_user_id,
            "quantity": offer.quantity, "unit": offer.unit, "price_per_unit": offer.price_per_unit,
            "currency": offer.currency, "message": offer.message, "status": offer.status,
            "created_at": offer.created_at}


@router.post("/stock/{stock_lot_id}/offers", status_code=201)
def submit_stock_offer(stock_lot_id: int, payload: StockOfferCreate, db: Db, user: CurrentUser):
    buyer_type = _buyer_type(db, user.id)
    if user.role != "buyer" or user.verification_status != "verified":
        raise HTTPException(status_code=403, detail="A verified buyer account is required")
    if buyer_type in {"aggregator", "storekeeper", "storage_operator"}:
        raise HTTPException(status_code=403, detail="This buyer profile cannot submit purchase offers")
    lot = db.query(AggregatorStockLot).filter(AggregatorStockLot.id == stock_lot_id, AggregatorStockLot.status == "available").first()
    if lot is None:
        raise HTTPException(status_code=404, detail="Available stock lot not found")
    if payload.unit != lot.unit:
        raise HTTPException(status_code=422, detail="Offer unit must match the stock lot unit")
    if payload.quantity > lot.quantity - lot.reserved_quantity:
        raise HTTPException(status_code=422, detail="Offer quantity exceeds currently available stock")
    offer = AggregatorStockOffer(stock_lot_id=lot.id, aggregator_user_id=lot.aggregator_user_id,
        buyer_user_id=user.id, quantity=payload.quantity, unit=payload.unit,
        price_per_unit=payload.price_per_unit, currency=payload.currency,
        message=payload.message.strip(), status="pending")
    db.add(offer)
    db.flush()
    db.add(AuditLog(actor_user_id=user.id, action="aggregator_stock.offer_submitted",
        subject_type="aggregator_stock_offer", subject_id=offer.id,
        details_json={"stock_lot_id": lot.id, "quantity": offer.quantity, "unit": offer.unit,
                     "price_per_unit": offer.price_per_unit, "currency": offer.currency}))
    db.commit()
    db.refresh(offer)
    return _offer_view(offer)


@router.get("/stock/offers")
def list_stock_offers(db: Db, user: CurrentUser):
    if user.role != "buyer" or user.verification_status != "verified":
        raise HTTPException(status_code=403, detail="A verified marketplace account is required")
    rows = db.query(AggregatorStockOffer).filter(
        (AggregatorStockOffer.aggregator_user_id == user.id) | (AggregatorStockOffer.buyer_user_id == user.id)
    ).order_by(AggregatorStockOffer.created_at.desc()).all()
    return [_offer_view(row) for row in rows]


@router.post("/stock/offers/{offer_id}/decision")
def decide_stock_offer(offer_id: int, payload: OfferDecision, db: Db, user: CurrentUser):
    if user.role != "buyer" or user.verification_status != "verified" or _buyer_type(db, user.id) not in {"aggregator", "storekeeper"}:
        raise HTTPException(status_code=403, detail="Only a verified aggregator/storekeeper can decide offers")
    offer = db.query(AggregatorStockOffer).filter(
        AggregatorStockOffer.id == offer_id, AggregatorStockOffer.aggregator_user_id == user.id
    ).with_for_update().first()
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    if offer.status != "pending":
        raise HTTPException(status_code=409, detail="Offer is no longer pending")
    offer.responded_at = datetime.now(UTC)
    if payload.decision == "reject":
        offer.status = "rejected"
        db.add(AuditLog(actor_user_id=user.id, action="aggregator_stock.offer_rejected",
            subject_type="aggregator_stock_offer", subject_id=offer.id,
            details_json={"message": payload.message.strip()}))
        db.commit()
        return {"offer_id": offer.id, "status": offer.status}
    reserved = db.execute(update(AggregatorStockLot).where(
        AggregatorStockLot.id == offer.stock_lot_id,
        AggregatorStockLot.status == "available",
        AggregatorStockLot.quantity - AggregatorStockLot.reserved_quantity >= offer.quantity,
    ).values(reserved_quantity=AggregatorStockLot.reserved_quantity + offer.quantity))
    if reserved.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Stock is no longer available in sufficient quantity")
    offer.status = "accepted"
    deal = AggregatorStockDeal(offer_id=offer.id, stock_lot_id=offer.stock_lot_id,
        aggregator_user_id=offer.aggregator_user_id, buyer_user_id=offer.buyer_user_id,
        quantity=offer.quantity, unit=offer.unit, price_per_unit=offer.price_per_unit,
        currency=offer.currency, status="reserved")
    db.add(deal)
    db.flush()
    db.add(AggregatorStockDealEvent(deal_id=deal.id, actor_user_id=user.id,
        event_type="offer_accepted_reserved",
        details_json={"quantity": deal.quantity, "unit": deal.unit,
                     "price_per_unit": deal.price_per_unit, "currency": deal.currency,
                     "message": payload.message.strip()}))
    db.add(AuditLog(actor_user_id=user.id, action="aggregator_stock.offer_accepted",
        subject_type="aggregator_stock_deal", subject_id=deal.id,
        details_json={"offer_id": offer.id, "stock_lot_id": offer.stock_lot_id,
                     "reserved_quantity": offer.quantity}))
    db.commit()
    db.refresh(deal)
    return {"offer_id": offer.id, "deal_id": deal.id, "status": deal.status,
            "reserved_quantity": deal.quantity, "unit": deal.unit,
            "total_value": deal.quantity * deal.price_per_unit, "currency": deal.currency}


@router.get("/stock/deals")
def list_stock_deals(db: Db, user: CurrentUser):
    if user.role != "buyer" or user.verification_status != "verified":
        raise HTTPException(status_code=403, detail="A verified marketplace account is required")
    rows = db.query(AggregatorStockDeal).filter(
        (AggregatorStockDeal.aggregator_user_id == user.id) | (AggregatorStockDeal.buyer_user_id == user.id)
    ).order_by(AggregatorStockDeal.created_at.desc()).all()
    return [{"id": row.id, "stock_lot_id": row.stock_lot_id, "offer_id": row.offer_id,
             "buyer_user_id": row.buyer_user_id, "aggregator_user_id": row.aggregator_user_id,
             "quantity": row.quantity, "unit": row.unit, "price_per_unit": row.price_per_unit,
             "currency": row.currency, "total_value": row.quantity * row.price_per_unit,
             "status": row.status, "created_at": row.created_at} for row in rows]


@router.post("/stock/deals/{deal_id}/cancel")
def cancel_stock_deal(deal_id: int, db: Db, user: CurrentUser):
    if user.role != "buyer" or user.verification_status != "verified":
        raise HTTPException(status_code=403, detail="A verified deal participant is required")
    deal = db.query(AggregatorStockDeal).filter(
        AggregatorStockDeal.id == deal_id,
        (AggregatorStockDeal.aggregator_user_id == user.id) | (AggregatorStockDeal.buyer_user_id == user.id)
    ).with_for_update().first()
    if deal is None:
        raise HTTPException(status_code=404, detail="Deal not found")
    if deal.status != "reserved":
        raise HTTPException(status_code=409, detail="Only reserved deals can be cancelled")
    released = db.execute(update(AggregatorStockLot).where(
        AggregatorStockLot.id == deal.stock_lot_id,
        AggregatorStockLot.reserved_quantity >= deal.quantity,
    ).values(reserved_quantity=AggregatorStockLot.reserved_quantity - deal.quantity))
    if released.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Reservation could not be safely released")
    deal.status = "cancelled"
    db.add(AggregatorStockDealEvent(deal_id=deal.id, actor_user_id=user.id,
        event_type="reservation_released", details_json={"quantity": deal.quantity, "unit": deal.unit}))
    db.add(AuditLog(actor_user_id=user.id, action="aggregator_stock.deal_cancelled",
        subject_type="aggregator_stock_deal", subject_id=deal.id,
        details_json={"released_quantity": deal.quantity}))
    db.commit()
    return {"deal_id": deal.id, "status": deal.status, "released_quantity": deal.quantity}
