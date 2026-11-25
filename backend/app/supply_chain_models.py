"""Aggregator-owned stock and independent storage-service records."""
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models import utc_now


class AggregatorStockLot(Base):
    __tablename__ = "aggregator_stock_lots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    aggregator_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    crop_name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    reserved_quantity: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    unit: Mapped[str] = mapped_column(String(12), nullable=False)
    quality_description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    location: Mapped[str] = mapped_column(String(180), nullable=False)
    source_listing_id: Mapped[int | None] = mapped_column(ForeignKey("produce_listings.id"))
    ownership_reference: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="available", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class StorageOperatorProfile(Base):
    __tablename__ = "storage_operator_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    facility_name: Mapped[str] = mapped_column(String(180), nullable=False)
    location: Mapped[str] = mapped_column(String(180), nullable=False)
    capacity_kg: Mapped[float] = mapped_column(Float, nullable=False)
    accepted_commodities: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class StorageBooking(Base):
    __tablename__ = "storage_bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_lot_id: Mapped[int] = mapped_column(ForeignKey("aggregator_stock_lots.id"), index=True)
    operator_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    requested_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    quantity_kg: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="requested", nullable=False)
    fee_amount: Mapped[float | None] = mapped_column(Float)
    fee_currency: Mapped[str | None] = mapped_column(String(3))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AgentExecutionRecord(Base):
    __tablename__ = "agent_execution_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_run_id: Mapped[int] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    requested_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    agent_name: Mapped[str] = mapped_column(String(60), nullable=False)
    run_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    events_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
