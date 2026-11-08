from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.orchestrator import execute_offer_workflow
from app.agents.schemas import (
    BuyerRequirementInput,
    ProduceOfferInput,
    WorkflowResponse,
)
from app.db import get_db
from app.dependencies import get_current_user
from app.models import (
    AgentTask, AuditLog, BuyerRequirement, ProduceListing, User, VerificationCase, WorkflowRun,
)

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


@router.post("/workflows/produce-offers", response_model=WorkflowResponse, status_code=201)
def submit_produce_offer(
    payload: ProduceOfferInput, db: DatabaseSession, user: CurrentUser
):
    if user.role != "farmer":
        raise HTTPException(status_code=403, detail="Only farmer accounts can submit offers")
    result = execute_offer_workflow(db, user.id, payload)
    db.add(VerificationCase(
        subject_type="listing", subject_id=result.listing_id,
        submitted_by_user_id=user.id, status="pending",
    ))
    db.add(AuditLog(
        actor_user_id=user.id, action="listing.submitted_for_review",
        subject_type="produce_listing", subject_id=result.listing_id,
        details_json={"workflow_run_id": result.workflow_run_id},
    ))
    db.commit()
    return result


@router.get("/workflows/{workflow_run_id}")
def get_workflow_run(workflow_run_id: int, db: DatabaseSession, user: CurrentUser):
    run = (
        db.query(WorkflowRun)
        .join(ProduceListing, WorkflowRun.listing_id == ProduceListing.id)
        .filter(
            WorkflowRun.id == workflow_run_id,
            ProduceListing.farmer_user_id == user.id,
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
        "result": run.result_json,
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
