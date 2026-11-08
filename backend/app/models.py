from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(30), default="farmer", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    verification_status: Mapped[str] = mapped_column(String(20), default="unverified", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class BuyerRequirement(Base):
    __tablename__ = "buyer_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    buyer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    crop_name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    min_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    max_quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    quality_requirements: Mapped[str] = mapped_column(Text, default="", nullable=False)
    location: Mapped[str] = mapped_column(String(180), nullable=False)
    max_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ProduceListing(Base):
    __tablename__ = "produce_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farmer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    crop_name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    quality_description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(String(180), nullable=False)
    available_on: Mapped[date] = mapped_column(Date, nullable=False)
    asking_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending_review", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int | None] = mapped_column(ForeignKey("produce_listings.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="running", nullable=False)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_run_id: Mapped[int] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    agent_name: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    output_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MatchCandidate(Base):
    __tablename__ = "match_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_run_id: Mapped[int] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    buyer_requirement_id: Mapped[int] = mapped_column(
        ForeignKey("buyer_requirements.id"), index=True
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reasons_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class BuyerProfile(Base):
    __tablename__ = "buyer_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    organization_name: Mapped[str] = mapped_column(String(180), nullable=False)
    buyer_type: Mapped[str] = mapped_column(String(40), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    location: Mapped[str] = mapped_column(String(180), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class VerificationCase(Base):
    __tablename__ = "verification_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    submitted_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(30), nullable=False)
    subject_id: Mapped[int] = mapped_column(Integer, nullable=False)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class FarmProfile(Base):
    __tablename__ = "farm_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farmer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    farm_name: Mapped[str] = mapped_column(String(160), nullable=False)
    location: Mapped[str] = mapped_column(String(180), nullable=False)
    acreage: Mapped[float] = mapped_column(Float, nullable=False)
    acreage_unit: Mapped[str] = mapped_column(String(20), default="hectare", nullable=False)
    land_access: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class FarmSeason(Base):
    __tablename__ = "farm_seasons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farmer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    farm_profile_id: Mapped[int] = mapped_column(ForeignKey("farm_profiles.id"), index=True, nullable=False)
    crop_name: Mapped[str] = mapped_column(String(100), nullable=False)
    season_name: Mapped[str] = mapped_column(String(100), nullable=False)
    planted_area: Mapped[float] = mapped_column(Float, nullable=False)
    area_unit: Mapped[str] = mapped_column(String(20), default="hectare", nullable=False)
    planting_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expected_harvest_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class FarmActivity(Base):
    __tablename__ = "farm_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farmer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    season_id: Mapped[int] = mapped_column(ForeignKey("farm_seasons.id"), index=True, nullable=False)
    activity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    activity_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantity_unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    source_channel: Mapped[str] = mapped_column(String(20), default="web", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class FarmEvidence(Base):
    __tablename__ = "farm_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farmer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    activity_id: Mapped[int] = mapped_column(ForeignKey("farm_activities.id"), index=True, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(30), nullable=False)
    evidence_uri: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    verification_level: Mapped[str] = mapped_column(String(30), default="document_supported", nullable=False)
    verified_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    verification_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class FarmShareGrant(Base):
    __tablename__ = "farm_share_grants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farmer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    season_id: Mapped[int | None] = mapped_column(ForeignKey("farm_seasons.id"), nullable=True)
    recipient_name: Mapped[str] = mapped_column(String(160), nullable=False)
    recipient_type: Mapped[str] = mapped_column(String(40), nullable=False)
    purpose: Mapped[str] = mapped_column(String(300), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class FarmShareAccess(Base):
    __tablename__ = "farm_share_accesses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grant_id: Mapped[int] = mapped_column(ForeignKey("farm_share_grants.id"), index=True, nullable=False)
    accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    access_type: Mapped[str] = mapped_column(String(30), default="report_view", nullable=False)
