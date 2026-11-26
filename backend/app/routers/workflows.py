import hashlib
import json
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.agents.schemas import (
    BuyerRequirementInput,
    ProduceOfferInput,
)
from app.db import get_db
from app.dependencies import get_current_user
from app.models import (
    AgentTask,
    AuditLog,
    BuyerRequirement,
    ProduceListing,
    User,
    VerificationCase,
    WorkflowRun,
)
from sqlalchemy.exc import IntegrityError

router = APIRouter(prefix="/api/v1", tags=["marketplace workflow"])
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("/buyer-requirements", status_code=201)
def create_buyer_requirement(
    payload: BuyerRequirementInput, db: DatabaseSession, user: CurrentUser
):
    if user.role != "buyer":
        raise HTTPException(status_code=403, detail="Only buyer accounts can create requirements")
    if user.verification_status != "verified":
        raise HTTPException(status_code=403, detail="Buyer verification approval is required")
    requirement = BuyerRequirement(
        buyer_user_id=user.id,
        **payload.model_dump(),
    )
    db.add(requirement)
    db.commit()
    db.refresh(requirement)
    return {
        "id": requirement.id,
        "crop_name": requirement.crop_name,
        "min_quantity": requirement.min_quantity,
        "max_quantity": requirement.max_quantity,
        "unit": requirement.unit,
        "location": requirement.location,
        "is_active": requirement.is_active,
    }


@router.get("/buyer-requirements")
def list_buyer_requirements(db: DatabaseSession, user: CurrentUser):
    items = (
        db.query(BuyerRequirement)
        .filter(BuyerRequirement.buyer_user_id == user.id)
        .order_by(BuyerRequirement.created_at.desc())
        .all()
    )
    return [
        {
            "id": item.id,
            "crop_name": item.crop_name,
            "min_quantity": item.min_quantity,
            "max_quantity": item.max_quantity,
            "unit": item.unit,
            "location": item.location,
            "is_active": item.is_active,
        }
        for item in items
    ]


@router.post("/workflows/produce-offers", status_code=202)
def submit_produce_offer(
    payload: ProduceOfferInput,
    db: DatabaseSession,
    user: CurrentUser,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
):
    if user.role != "farmer":
        raise HTTPException(status_code=403, detail="Only farmer accounts can submit offers")

    request_data = payload.model_dump(mode="json")
    canonical = json.dumps(request_data, sort_keys=True, separators=(",", ":"))
    request_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    existing = db.query(WorkflowRun).filter(
        WorkflowRun.farmer_user_id == user.id,
        WorkflowRun.idempotency_key == idempotency_key,
    ).first()
    if existing:
        if existing.request_hash != request_hash:
            raise HTTPException(
                status_code=409,
                detail="This Idempotency-Key was already used with a different offer",
            )
        return {
            "workflow_run_id": existing.id,
            "status": existing.status,
            "listing_id": existing.listing_id,
            "duplicate_request": True,
        }

    run = WorkflowRun(
        farmer_user_id=user.id,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        status="queued",
        result_json={"request": request_data},
        attempt_count=0,
        max_attempts=5,
    )
    db.add(run)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(WorkflowRun).filter(
            WorkflowRun.farmer_user_id == user.id,
            WorkflowRun.idempotency_key == idempotency_key,
        ).first()
        if existing is None:
            raise
        if existing.request_hash != request_hash:
            raise HTTPException(
                status_code=409,
                detail="This Idempotency-Key was already used with a different offer",
            )
        return {
            "workflow_run_id": existing.id,
            "status": existing.status,
            "listing_id": existing.listing_id,
            "duplicate_request": True,
        }
    db.refresh(run)
    return {
        "workflow_run_id": run.id,
        "status": run.status,
        "listing_id": run.listing_id,
        "duplicate_request": False,
        "poll_url": f"/api/v1/workflows/{run.id}",
    }


@router.get("/workflows/{workflow_run_id}")
def get_workflow_run(workflow_run_id: int, db: DatabaseSession, user: CurrentUser):
    run = (
        db.query(WorkflowRun)
        .filter(
            WorkflowRun.id == workflow_run_id,
            WorkflowRun.farmer_user_id == user.id,
        )
        .first()
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    tasks = (
        db.query(AgentTask)
        .filter(AgentTask.workflow_run_id == run.id)
        .order_by(AgentTask.id.asc())
        .all()
    )
    return {
        "workflow_run_id": run.id,
        "listing_id": run.listing_id,
        "status": run.status,
        "result": run.result_json.get("response"),
        "attempt_count": run.attempt_count,
        "max_attempts": run.max_attempts,
        "next_retry_at": run.next_retry_at,
        "last_error": run.last_error,
        "agent_tasks": [
            {
                "task_id": task.id,
                "agent_name": task.agent_name,
                "status": task.status,
                "input": task.input_json,
                "output": task.output_json,
                "error": task.error_message,
            }
            for task in tasks
        ],
    }
