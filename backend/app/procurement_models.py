from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models import utc_now


class BuyerInterest(Base):
    __tablename__ = "buyer_interests"
    __table_args__ = (UniqueConstraint("match_candidate_id", name="uq_buyer_interest_match"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_candidate_id: Mapped[int] = mapped_column(ForeignKey("match_candidates.id"), index=True)
    buyer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    farmer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    buyer_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    farmer_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProcurementTransaction(Base):
    __tablename__ = "procurement_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    interest_id: Mapped[int] = mapped_column(ForeignKey("buyer_interests.id"), unique=True, index=True)
    buyer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    farmer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("produce_listings.id"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="terms_proposed", nullable=False)
    proposed_terms_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    agreed_terms_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TransactionEvent(Base):
    __tablename__ = "transaction_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("procurement_transactions.id"), index=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class LogisticsProviderProfile(Base):
    __tablename__ = "logistics_provider_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    organization_name: Mapped[str] = mapped_column(String(180), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    service_areas: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    transport_modes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class LogisticsQuoteRequest(Base):
    __tablename__ = "logistics_quote_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("procurement_transactions.id"), index=True)
    requested_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    origin: Mapped[str] = mapped_column(String(180), nullable=False)
    destination: Mapped[str] = mapped_column(String(180), nullable=False)
    pickup_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cargo_description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class LogisticsQuote(Base):
    __tablename__ = "logistics_quotes"
    __table_args__ = (UniqueConstraint("request_id", "provider_user_id", name="uq_logistics_quote_provider"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("logistics_quote_requests.id"), index=True)
    provider_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    estimated_days: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="submitted", nullable=False)
    buyer_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    farmer_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
