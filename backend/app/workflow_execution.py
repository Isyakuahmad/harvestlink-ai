"""Database-backed, resumable execution for marketplace offer workflows."""
from datetime import UTC, datetime, timedelta
import time

from fastapi.encoders import jsonable_encoder
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.agents.buyer_matching import find_matches
from app.agents.farmer import structure_offer
from app.agents.schemas import ProduceOfferInput, TrustAssessment, WorkflowResponse
from app.agents.trust import assess_listing
from app.db import SessionLocal
from app.models import (
    AgentTask,
    AuditLog,
    BuyerRequirement,
    MatchCandidate,
    ProduceListing,
    User,
    VerificationCase,
    WorkflowRun,
)


def _now() -> datetime:
    return datetime.now(UTC)


def claim_next_workflow(db: Session, stale_after_seconds: int = 300) -> int | None:
    """Claim one due run. A stale running claim is recoverable after worker death."""
    now = _now()
    stale_before = now - timedelta(seconds=stale_after_seconds)
    run = (
        db.query(WorkflowRun)
        .filter(
            or_(
                WorkflowRun.status.in_(("queued", "retrying"))
                & or_(WorkflowRun.next_retry_at.is_(None), WorkflowRun.next_retry_at <= now),
                (WorkflowRun.status == "running")
                & (WorkflowRun.locked_at.is_not(None))
                & (WorkflowRun.locked_at <= stale_before),
            )
        )
        .order_by(WorkflowRun.created_at.asc())
        .with_for_update(skip_locked=True)
        .first()
    )
    if run is None:
        return None
    run.status = "running"
    run.locked_at = now
    run.attempt_count += 1
    run.next_retry_at = None
    db.commit()
    return run.id


def _completed_task(db: Session, run_id: int, name: str) -> dict | None:
    task = (
        db.query(AgentTask)
        .filter(
            AgentTask.workflow_run_id == run_id,
            AgentTask.agent_name == name,
            AgentTask.status == "completed",
        )
        .order_by(AgentTask.id.desc())
        .first()
    )
    return task.output_json if task else None


def _save_task(db: Session, run_id: int, name: str, task_input: dict, output: dict) -> None:
    db.add(
        AgentTask(
            workflow_run_id=run_id,
            agent_name=name,
            status="completed",
            input_json=jsonable_encoder(task_input),
            output_json=jsonable_encoder(output),
            completed_at=_now(),
        )
    )
    db.commit()


def process_workflow(db: Session, run_id: int) -> bool:
    """Execute completed checkpoints once; return True when the run is complete."""
    run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).one()
    if run.status == "completed":
        return True
    request_data = run.result_json.get("request")
    if not request_data:
        raise ValueError("Workflow run is missing its persisted request payload")
    payload = ProduceOfferInput.model_validate(request_data)

    offer = _completed_task(db, run_id, "farmer")
    if offer is None:
        offer = structure_offer(payload)
        if run.listing_id is None:
            listing = ProduceListing(
                farmer_user_id=run.farmer_user_id,
                **offer,
                status="pending_review",
            )
            db.add(listing)
            db.flush()
            run.listing_id = listing.id
        _save_task(
            db, run_id, "farmer", request_data,
            {**offer, "available_on": offer["available_on"].isoformat()},
        )
        db.refresh(run)
    else:
        offer["available_on"] = payload.available_on

    trust_data = _completed_task(db, run_id, "trust")
    if trust_data is None:
        farmer = db.query(User).filter(User.id == run.farmer_user_id).one()
        trust = assess_listing(
            offer, identity_verified=farmer.verification_status == "verified"
        )
        trust_data = trust.model_dump(mode="json")
        _save_task(db, run_id, "trust", offer, trust_data)
    trust = TrustAssessment.model_validate(trust_data)

    match_data = _completed_task(db, run_id, "buyer_matching")
    if match_data is None:
        requirements = (
            db.query(BuyerRequirement)
            .join(User, BuyerRequirement.buyer_user_id == User.id)
            .filter(
                BuyerRequirement.is_active.is_(True),
                User.verification_status == "verified",
            )
            .all()
        )
        matches = find_matches(offer, requirements)
        for match in matches:
            db.add(
                MatchCandidate(
                    workflow_run_id=run_id,
                    buyer_requirement_id=match.buyer_requirement_id,
                    score=match.score,
                    eligible=match.eligible,
                    reasons_json=match.reasons,
                )
            )
        match_data = {"matches": [item.model_dump(mode="json") for item in matches]}
        _save_task(
            db, run_id, "buyer_matching",
            {"listing_id": run.listing_id, "active_requirements": len(requirements)},
            match_data,
        )

    matches = match_data["matches"]
    next_action = (
        "Manual identity and listing review is required before publication or buyer contact."
    )
    response = {
        "workflow_run_id": run.id,
        "listing_id": run.listing_id,
        "workflow_status": "completed",
        "listing_status": "pending_review",
        "trust": trust.model_dump(mode="json"),
        "matches": matches,
        "next_action": next_action,
    }
    run.status = "completed"
    run.result_json = {"request": request_data, "response": response}
    run.completed_at = _now()
    run.locked_at = None
    run.last_error = None
    db.add(
        VerificationCase(
            subject_type="listing",
            subject_id=run.listing_id,
            submitted_by_user_id=run.farmer_user_id,
            status="pending",
        )
    )
    db.add(
        AuditLog(
            actor_user_id=run.farmer_user_id,
            action="listing.submitted_for_review",
            subject_type="produce_listing",
            subject_id=run.listing_id,
            details_json={"workflow_run_id": run.id},
        )
    )
    _save_task(
        db, run_id, "orchestrator",
        {"workflow_run_id": run.id},
        {"status": "completed", "next_action": next_action},
    )
    db.commit()
    return True


def run_one_workflow(db: Session) -> int | None:
    run_id = claim_next_workflow(db)
    if run_id is None:
        return None
    try:
        process_workflow(db, run_id)
    except Exception as exc:
        db.rollback()
        run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).one()
        run.last_error = str(exc)[:4000]
        run.locked_at = None
        if run.attempt_count >= run.max_attempts:
            run.status = "failed"
            run.next_retry_at = None
        else:
            run.status = "retrying"
            delay = min(300, 2 ** max(0, run.attempt_count - 1))
            run.next_retry_at = _now() + timedelta(seconds=delay)
        db.commit()
    return run_id


def run_pending_once(session_factory=SessionLocal) -> int | None:
    """Run one queued workflow using an injectable session factory (also used by tests)."""
    db = session_factory()
    try:
        return run_one_workflow(db)
    finally:
        db.close()


def run_forever(poll_seconds: float = 2.0) -> None:
    while True:
        claimed = run_pending_once()
        if claimed is None:
            time.sleep(poll_seconds)


if __name__ == "__main__":
    run_forever()
