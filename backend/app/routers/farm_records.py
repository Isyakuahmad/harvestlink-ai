from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from urllib.parse import urlsplit
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_user
from app.models import (
    AuditLog, FarmActivity, FarmEvidence, FarmProfile, FarmSeason,
    FarmShareAccess, FarmShareGrant, User,
)
from app.schemas import (
    FarmActivityCreate, FarmEvidenceCreate, FarmProfileCreate,
    FarmSeasonCreate, FarmShareCreate,
)

router = APIRouter(prefix="/api/v1/farm-records", tags=["farmer records"])
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def require_farmer(user: CurrentUser) -> User:
    if user.role != "farmer":
        raise HTTPException(status_code=403, detail="Farmer account required")
    return user


FarmerUser = Annotated[User, Depends(require_farmer)]


def _date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{field} must use YYYY-MM-DD") from None


def _owned_season(db: Session, farmer_id: int, season_id: int) -> FarmSeason:
    season = db.query(FarmSeason).filter(
        FarmSeason.id == season_id, FarmSeason.farmer_user_id == farmer_id
    ).first()
    if season is None:
        raise HTTPException(status_code=404, detail="Farm season not found")
    return season


def _report(db: Session, farmer_id: int, season_id: int | None = None) -> dict:
    seasons_query = db.query(FarmSeason).filter(FarmSeason.farmer_user_id == farmer_id)
    if season_id is not None:
        seasons_query = seasons_query.filter(FarmSeason.id == season_id)
    seasons = seasons_query.order_by(FarmSeason.created_at.asc()).all()
    if season_id is not None and not seasons:
        raise HTTPException(status_code=404, detail="Farm season not found")
    result = []
    for season in seasons:
        activities = db.query(FarmActivity).filter(
            FarmActivity.season_id == season.id,
            FarmActivity.farmer_user_id == farmer_id,
        ).order_by(FarmActivity.activity_date.asc(), FarmActivity.id.asc()).all()
        entries = []
        for activity in activities:
            evidence = db.query(FarmEvidence).filter(
                FarmEvidence.activity_id == activity.id,
                FarmEvidence.farmer_user_id == farmer_id,
            ).all()
            entries.append({
                "id": activity.id, "type": activity.activity_type,
                "description": activity.description, "date": activity.activity_date,
                "quantity": activity.quantity, "quantity_unit": activity.quantity_unit,
                "amount": activity.amount, "currency": activity.currency,
                "source_channel": activity.source_channel,
                "evidence": [{
                    "id": item.id, "type": item.evidence_type,
                    "description": item.description,
                    "verification_level": item.verification_level,
                    "uri": item.evidence_uri,
                } for item in evidence],
                "record_confidence": (
                    "independently_verified" if any(
                        item.verification_level == "independently_verified" for item in evidence
                    ) else "document_supported" if evidence else "self_reported"
                ),
            })
        income = sum(
            (a.amount or 0) for a in activities if a.activity_type in {"sale", "delivery"}
        )
        expenses = sum(
            (a.amount or 0) for a in activities
            if a.activity_type in {"input_purchase", "labour", "other"}
        )
        result.append({
            "season_id": season.id, "crop_name": season.crop_name,
            "season_name": season.season_name, "planted_area": season.planted_area,
            "area_unit": season.area_unit, "planting_date": season.planting_date,
            "expected_harvest_date": season.expected_harvest_date,
            "status": season.status, "activities": entries,
            "totals": {"recorded_income": income, "recorded_expenses": expenses,
                       "recorded_net": income - expenses},
            "disclaimer": "Totals include only amounts entered in HarvestLink; they are not audited accounts.",
        })
    return {"farmer_user_id": farmer_id, "generated_at": datetime.now(UTC),
            "evidence_standard": {
                "self_reported": "Farmer-entered record without attached evidence.",
                "document_supported": "A document or photo is attached; authenticity is not independently established.",
                "independently_verified": "A permitted HarvestLink reviewer has recorded a verification decision.",
            }, "seasons": result}


@router.post("/farms", status_code=201)
def create_farm(payload: FarmProfileCreate, db: DatabaseSession, farmer: FarmerUser):
    farm = FarmProfile(farmer_user_id=farmer.id, **payload.model_dump())
    db.add(farm)
    db.commit()
    db.refresh(farm)
    return {"id": farm.id, "farm_name": farm.farm_name, "location": farm.location,
            "acreage": farm.acreage, "acreage_unit": farm.acreage_unit,
            "land_access": farm.land_access}


@router.get("/farms")
def list_farms(db: DatabaseSession, farmer: FarmerUser):
    farms = db.query(FarmProfile).filter(FarmProfile.farmer_user_id == farmer.id).all()
    return [{"id": f.id, "farm_name": f.farm_name, "location": f.location,
             "acreage": f.acreage, "acreage_unit": f.acreage_unit,
             "land_access": f.land_access} for f in farms]


@router.post("/seasons", status_code=201)
def create_season(payload: FarmSeasonCreate, db: DatabaseSession, farmer: FarmerUser):
    farm = db.query(FarmProfile).filter(
        FarmProfile.id == payload.farm_profile_id,
        FarmProfile.farmer_user_id == farmer.id,
    ).first()
    if farm is None:
        raise HTTPException(status_code=404, detail="Farm profile not found")
    values = payload.model_dump()
    planting = _date(values.pop("planting_date"), "planting_date") if values["planting_date"] else None
    harvest = _date(values.pop("expected_harvest_date"), "expected_harvest_date") if values["expected_harvest_date"] else None
    if planting and harvest and harvest < planting:
        raise HTTPException(status_code=422, detail="Expected harvest cannot precede planting")
    season = FarmSeason(farmer_user_id=farmer.id, planting_date=planting,
                        expected_harvest_date=harvest, **values)
    db.add(season)
    db.commit()
    db.refresh(season)
    return {"id": season.id, "crop_name": season.crop_name, "season_name": season.season_name,
            "status": season.status}


@router.get("/seasons")
def list_seasons(db: DatabaseSession, farmer: FarmerUser):
    seasons = db.query(FarmSeason).filter(FarmSeason.farmer_user_id == farmer.id).all()
    return [{"id": s.id, "farm_profile_id": s.farm_profile_id, "crop_name": s.crop_name,
             "season_name": s.season_name, "planted_area": s.planted_area,
             "area_unit": s.area_unit, "planting_date": s.planting_date,
             "expected_harvest_date": s.expected_harvest_date, "status": s.status}
            for s in seasons]


@router.post("/seasons/{season_id}/activities", status_code=201)
def add_activity(season_id: int, payload: FarmActivityCreate,
                 db: DatabaseSession, farmer: FarmerUser):
    _owned_season(db, farmer.id, season_id)
    values = payload.model_dump()
    values.pop("season_id")
    activity = FarmActivity(
        farmer_user_id=farmer.id, season_id=season_id,
        activity_date=_date(values.pop("activity_date"), "activity_date"), **values,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return {"id": activity.id, "season_id": season_id,
            "record_confidence": "self_reported", "created_at": activity.created_at}


@router.get("/seasons/{season_id}/activities")
def list_activities(season_id: int, db: DatabaseSession, farmer: FarmerUser):
    _owned_season(db, farmer.id, season_id)
    activities = db.query(FarmActivity).filter(
        FarmActivity.season_id == season_id, FarmActivity.farmer_user_id == farmer.id
    ).order_by(FarmActivity.activity_date.desc()).all()
    return [{"id": a.id, "activity_type": a.activity_type, "description": a.description,
             "activity_date": a.activity_date, "quantity": a.quantity,
             "quantity_unit": a.quantity_unit, "amount": a.amount, "currency": a.currency}
            for a in activities]


@router.post("/activities/{activity_id}/evidence", status_code=201)
def add_evidence(activity_id: int, payload: FarmEvidenceCreate,
                 db: DatabaseSession, farmer: FarmerUser):
    activity = db.query(FarmActivity).filter(
        FarmActivity.id == activity_id, FarmActivity.farmer_user_id == farmer.id
    ).first()
    if activity is None:
        raise HTTPException(status_code=404, detail="Farm activity not found")
    parsed = urlsplit(payload.evidence_uri)
    if parsed.scheme != "https" or not parsed.netloc:
        raise HTTPException(status_code=422, detail="Evidence URI must be an HTTPS URL")
    evidence = FarmEvidence(
        farmer_user_id=farmer.id, activity_id=activity.id,
        evidence_type=payload.evidence_type, evidence_uri=payload.evidence_uri,
        description=payload.description, verification_level="document_supported",
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return {"id": evidence.id, "verification_level": evidence.verification_level,
            "note": "Attachment is document-supported, not independently authenticated."}


@router.get("/report")
def own_report(db: DatabaseSession, farmer: FarmerUser,
               season_id: int | None = Query(default=None, gt=0)):
    return _report(db, farmer.id, season_id)


@router.post("/sharing", status_code=201)
def create_share(payload: FarmShareCreate, db: DatabaseSession, farmer: FarmerUser):
    if payload.season_id is not None:
        _owned_season(db, farmer.id, payload.season_id)
    raw_token = token_urlsafe(32)
    grant = FarmShareGrant(
        farmer_user_id=farmer.id, season_id=payload.season_id,
        recipient_name=payload.recipient_name, recipient_type=payload.recipient_type,
        purpose=payload.purpose, token_hash=sha256(raw_token.encode()).hexdigest(),
        expires_at=datetime.now(UTC) + timedelta(days=payload.expires_in_days),
    )
    db.add(grant)
    db.flush()
    db.add(AuditLog(actor_user_id=farmer.id, action="farm_records.share_granted",
                    subject_type="farm_share_grant", subject_id=grant.id,
                    details_json={"recipient_type": grant.recipient_type,
                                  "recipient_name": grant.recipient_name,
                                  "season_id": grant.season_id, "purpose": grant.purpose}))
    db.commit()
    return {"share_id": grant.id, "access_token": raw_token,
            "expires_at": grant.expires_at,
            "warning": "Treat this token like a private document link. Anyone with it can view the approved report scope."}


@router.get("/sharing")
def list_shares(db: DatabaseSession, farmer: FarmerUser):
    grants = db.query(FarmShareGrant).filter(
        FarmShareGrant.farmer_user_id == farmer.id
    ).order_by(FarmShareGrant.created_at.desc()).all()
    return [{"id": g.id, "recipient_name": g.recipient_name,
             "recipient_type": g.recipient_type, "purpose": g.purpose,
             "season_id": g.season_id, "expires_at": g.expires_at,
             "revoked": g.revoked_at is not None} for g in grants]


@router.delete("/sharing/{share_id}", status_code=204)
def revoke_share(share_id: int, db: DatabaseSession, farmer: FarmerUser):
    grant = db.query(FarmShareGrant).filter(
        FarmShareGrant.id == share_id, FarmShareGrant.farmer_user_id == farmer.id
    ).first()
    if grant is None:
        raise HTTPException(status_code=404, detail="Share grant not found")
    if grant.revoked_at is None:
        grant.revoked_at = datetime.now(UTC)
        db.add(AuditLog(actor_user_id=farmer.id, action="farm_records.share_revoked",
                        subject_type="farm_share_grant", subject_id=grant.id,
                        details_json={"recipient_type": grant.recipient_type}))
        db.commit()
    return None


@router.get("/shared/{access_token}")
def shared_report(access_token: str, db: DatabaseSession):
    token_hash = sha256(access_token.encode()).hexdigest()
    grant = db.query(FarmShareGrant).filter(FarmShareGrant.token_hash == token_hash).first()
    now = datetime.now(UTC)
    if grant is not None and grant.expires_at.tzinfo is None:
        grant.expires_at = grant.expires_at.replace(tzinfo=UTC)
    if grant is None or grant.revoked_at is not None or grant.expires_at <= now:
        raise HTTPException(status_code=404, detail="This shared report link is invalid or expired")
    db.add(FarmShareAccess(grant_id=grant.id))
    db.commit()
    return {"recipient": grant.recipient_name, "purpose": grant.purpose,
            "report": _report(db, grant.farmer_user_id, grant.season_id)}


@router.post("/admin/evidence/{evidence_id}/verify")
def verify_evidence(evidence_id: int, reason: str = Query(min_length=5, max_length=1000),
                    db: DatabaseSession = Depends(get_db),
                    reviewer: User = Depends(get_current_user)):
    if reviewer.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    evidence = db.query(FarmEvidence).filter(FarmEvidence.id == evidence_id).first()
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    if evidence.verification_level == "independently_verified":
        raise HTTPException(status_code=409, detail="Evidence is already independently verified")
    evidence.verification_level = "independently_verified"
    evidence.verified_by_user_id = reviewer.id
    evidence.verification_note = reason.strip()
    db.add(AuditLog(actor_user_id=reviewer.id, action="farm_evidence.independently_verified",
                    subject_type="farm_evidence", subject_id=evidence.id,
                    details_json={"reason": reason.strip(), "farmer_user_id": evidence.farmer_user_id}))
    db.commit()
    return {"evidence_id": evidence.id, "verification_level": evidence.verification_level,
            "verified_by_user_id": reviewer.id, "verification_note": evidence.verification_note}
