"""Authenticated aggregator inventory, independent storage and agent trace APIs."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agents.rules import get_rulebook
from app.agents.runtime import AgentRuntime, build_default_registry
from app.db import get_db
from app.dependencies import get_current_user
from app.models import BuyerProfile, ProduceListing, User, WorkflowRun
from app.supply_chain_models import (
    AgentExecutionRecord,
    AggregatorStockLot,
    StorageBooking,
    StorageOperatorProfile,
)

router = APIRouter(prefix="/api/v1", tags=["supply-chain"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


class StockCreate(BaseModel):
    crop_name: str = Field(min_length=2, max_length=100)
    quantity: float = Field(gt=0)
    unit: str = Field(pattern="^(kg|tonne)$")
    quality_description: str = Field(default="", max_length=2000)
    location: str = Field(min_length=2, max_length=180)
    ownership_reference: str = Field(min_length=2, max_length=120)
    source_listing_id: int | None = None


class StorageProfileCreate(BaseModel):
    facility_name: str = Field(min_length=2, max_length=180)
    location: str = Field(min_length=2, max_length=180)
    capacity_kg: float = Field(gt=0)
    accepted_commodities: list[str] = Field(min_length=1, max_length=30)


class StorageBookingCreate(BaseModel):
    stock_lot_id: int
    quantity_kg: float = Field(gt=0)


class AgentRunCreate(BaseModel):
    workflow_run_id: int
    agent_name: str = Field(min_length=2, max_length=60)
    task: str = Field(min_length=1, max_length=1000)


def _buyer_type(db: Session, user_id: int) -> str | None:
    profile = db.query(BuyerProfile).filter(BuyerProfile.user_id == user_id).first()
    return profile.buyer_type.lower() if profile else None


@router.post("/aggregator/stock", status_code=201)
def create_stock(payload: StockCreate, db: Db, user: CurrentUser):
    if user.role != "buyer" or user.verification_status != "verified":
        raise HTTPException(status_code=403, detail="A verified buyer account is required")
    if _buyer_type(db, user.id) not in {"aggregator", "storekeeper"}:
        raise HTTPException(status_code=403, detail="An approved aggregator/storekeeper profile is required")
    if payload.source_listing_id is not None:
        listing = db.query(ProduceListing).filter(
            ProduceListing.id == payload.source_listing_id,
            ProduceListing.status == "approved",
        ).first()
        if listing is None:
            raise HTTPException(status_code=404, detail="Approved source listing not found")
    lot = AggregatorStockLot(
        aggregator_user_id=user.id,
        crop_name=payload.crop_name.strip().lower(),
        quantity=payload.quantity,
        unit=payload.unit,
        quality_description=payload.quality_description.strip(),
        location=payload.location.strip(),
        ownership_reference=payload.ownership_reference.strip(),
        source_listing_id=payload.source_listing_id,
        status="available",
    )
    db.add(lot)
    db.commit()
    db.refresh(lot)
    return {"id": lot.id, "crop_name": lot.crop_name, "quantity": lot.quantity,
            "reserved_quantity": lot.reserved_quantity,
            "available_quantity": lot.quantity - lot.reserved_quantity,
            "unit": lot.unit, "location": lot.location, "status": lot.status,
            "owner_user_id": lot.aggregator_user_id}


@router.get("/marketplace/aggregator-stock")
def list_aggregator_stock(db: Db, user: CurrentUser):
    if user.role != "buyer" or user.verification_status != "verified":
        raise HTTPException(status_code=403, detail="A verified buyer account is required")
    lots = db.query(AggregatorStockLot).filter(
        AggregatorStockLot.status == "available"
    ).order_by(AggregatorStockLot.created_at.desc()).all()
    return [{"id": lot.id, "crop_name": lot.crop_name, "quantity": lot.quantity,
             "reserved_quantity": lot.reserved_quantity,
             "available_quantity": lot.quantity - lot.reserved_quantity,
             "unit": lot.unit, "quality_description": lot.quality_description,
             "location": lot.location} for lot in lots]


@router.post("/storage/profile", status_code=201)
def create_storage_profile(payload: StorageProfileCreate, db: Db, user: CurrentUser):
    if user.role != "buyer" or user.verification_status != "verified":
        raise HTTPException(status_code=403, detail="A verified account is required")
    if _buyer_type(db, user.id) != "storage_operator":
        raise HTTPException(status_code=403, detail="A verified storage-operator buyer profile is required")
    existing = db.query(StorageOperatorProfile).filter(
        StorageOperatorProfile.user_id == user.id
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Storage profile already exists")
    profile = StorageOperatorProfile(
        user_id=user.id, facility_name=payload.facility_name.strip(),
        location=payload.location.strip(), capacity_kg=payload.capacity_kg,
        accepted_commodities=[item.strip().lower() for item in payload.accepted_commodities],
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return {"id": profile.id, "facility_name": profile.facility_name,
            "location": profile.location, "capacity_kg": profile.capacity_kg}


@router.post("/storage/bookings", status_code=201)
def request_storage(payload: StorageBookingCreate, db: Db, user: CurrentUser):
    lot = db.query(AggregatorStockLot).filter(
        AggregatorStockLot.id == payload.stock_lot_id,
        AggregatorStockLot.status == "available",
    ).first()
    if lot is None:
        raise HTTPException(status_code=404, detail="Available aggregator stock not found")
    if user.role != "buyer" or user.verification_status != "verified":
        raise HTTPException(status_code=403, detail="A verified marketplace participant is required")
    if _buyer_type(db, user.id) == "storage_operator":
        raise HTTPException(status_code=403, detail="Storage operators cannot request storage for stock")
    if payload.quantity_kg > lot.quantity * (1000 if lot.unit == "tonne" else 1):
        raise HTTPException(status_code=422, detail="Storage quantity exceeds stock quantity")
    operators = db.query(StorageOperatorProfile).all()
    compatible = None
    for operator in operators:
        if lot.crop_name not in operator.accepted_commodities:
            continue
        committed = db.query(func.coalesce(func.sum(StorageBooking.quantity_kg), 0)).filter(
            StorageBooking.operator_user_id == operator.user_id,
            StorageBooking.status.in_(["requested", "accepted"]),
        ).scalar()
        if committed + payload.quantity_kg <= operator.capacity_kg:
            compatible = operator
            break
    if compatible is None:
        raise HTTPException(status_code=404, detail="No compatible storage operator with available capacity found")
    booking = StorageBooking(
        stock_lot_id=lot.id, operator_user_id=compatible.user_id,
        requested_by_user_id=user.id, quantity_kg=payload.quantity_kg,
        status="requested",
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return {"id": booking.id, "status": booking.status,
            "operator_user_id": booking.operator_user_id,
            "ownership_remains_with": lot.aggregator_user_id}


@router.post("/storage/bookings/{booking_id}/accept")
def accept_storage_booking(booking_id: int, db: Db, user: CurrentUser):
    profile = db.query(StorageOperatorProfile).filter(
        StorageOperatorProfile.user_id == user.id
    ).first()
    if user.role != "buyer" or user.verification_status != "verified" or profile is None:
        raise HTTPException(status_code=403, detail="A verified storage operator is required")
    booking = db.query(StorageBooking).filter(
        StorageBooking.id == booking_id, StorageBooking.operator_user_id == user.id
    ).first()
    if booking is None:
        raise HTTPException(status_code=404, detail="Storage request not found")
    if booking.status != "requested":
        raise HTTPException(status_code=409, detail="Storage request is no longer pending")
    booking.status = "accepted"
    db.commit()
    return {"id": booking.id, "status": booking.status, "stock_lot_id": booking.stock_lot_id}


@router.post("/workflows/agent-runs", status_code=201)
def run_workflow_agent(payload: AgentRunCreate, db: Db, user: CurrentUser):
    workflow = db.query(WorkflowRun).filter(
        WorkflowRun.id == payload.workflow_run_id
    ).first()
    if workflow is None or workflow.listing_id is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    listing = db.query(ProduceListing).filter(
        ProduceListing.id == workflow.listing_id,
        ProduceListing.farmer_user_id == user.id,
    ).first()
    if listing is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    try:
        rulebook = get_rulebook(payload.agent_name)
        tool_name = "normalize_crop_name" if payload.agent_name in {"farmer", "buyer_matching"} else "get_agent_capabilities"
        if tool_name not in rulebook.allowed_tools:
            raise HTTPException(status_code=422, detail="This agent has no safe executable tool configured")
        registry = build_default_registry()
        trace = AgentRuntime(registry).execute(
            payload.agent_name,
            [{"tool": tool_name, "arguments": {"crop_name": listing.crop_name} if tool_name == "normalize_crop_name" else {}}],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record = AgentExecutionRecord(
        workflow_run_id=workflow.id, requested_by_user_id=user.id,
        agent_name=trace.agent, run_id=trace.run_id, status=trace.status,
        events_json=trace.events,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"id": record.id, "run_id": record.run_id, "agent_name": record.agent_name,
            "status": record.status, "events": record.events_json}


@router.get("/workflows/{workflow_run_id}/agent-runs")
def list_workflow_agent_runs(workflow_run_id: int, db: Db, user: CurrentUser):
    workflow = db.query(WorkflowRun).filter(
        WorkflowRun.id == workflow_run_id
    ).first()
    if workflow is None or workflow.listing_id is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    listing = db.query(ProduceListing).filter(
        ProduceListing.id == workflow.listing_id,
        ProduceListing.farmer_user_id == user.id,
    ).first()
    if listing is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    rows = db.query(AgentExecutionRecord).filter(
        AgentExecutionRecord.workflow_run_id == workflow_run_id,
        AgentExecutionRecord.requested_by_user_id == user.id,
    ).order_by(AgentExecutionRecord.created_at.asc()).all()
    return [{"run_id": row.run_id, "agent_name": row.agent_name,
             "status": row.status, "events": row.events_json} for row in rows]
