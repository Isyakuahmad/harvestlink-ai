from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
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
