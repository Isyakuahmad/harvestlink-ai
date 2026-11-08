from datetime import UTC, datetime

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.agents.buyer_matching import find_matches
from app.agents.farmer import structure_offer
from app.agents.schemas import ProduceOfferInput, WorkflowResponse
from app.agents.trust import assess_listing
from app.models import AgentTask, BuyerRequirement, MatchCandidate, ProduceListing, WorkflowRun


def _record_task(db: Session, run_id: int, name: str, task_input: dict, output: dict) -> None:
    db.add(
        AgentTask(
            workflow_run_id=run_id,
            agent_name=name,
            status="completed",
            input_json=jsonable_encoder(task_input),
            output_json=jsonable_encoder(output),
            completed_at=datetime.now(UTC),
        )
    )
    db.flush()


def execute_offer_workflow(
    db: Session, farmer_user_id: int, payload: ProduceOfferInput
) -> WorkflowResponse:
    raw_input = payload.model_dump(mode="json")
    run = WorkflowRun(status="running", result_json={})
    db.add(run)
    db.flush()

    try:
        offer = structure_offer(payload)
        listing = ProduceListing(
            farmer_user_id=farmer_user_id,
            **offer,
            status="pending_review",
        )
        db.add(listing)
        db.flush()
        run.listing_id = listing.id
        _record_task(
            db, run.id, "farmer",
            raw_input,
            {**offer, "available_on": offer["available_on"].isoformat()},
        )

        trust = assess_listing(offer, identity_verified=False)
        _record_task(db, run.id, "trust", offer, trust.model_dump())

        requirements = (
            db.query(BuyerRequirement)
            .filter(BuyerRequirement.is_active.is_(True))
            .all()
        )
        matches = find_matches(offer, requirements)
        for match in matches:
            db.add(
                MatchCandidate(
                    workflow_run_id=run.id,
                    buyer_requirement_id=match.buyer_requirement_id,
                    score=match.score,
                    eligible=match.eligible,
                    reasons_json=match.reasons,
                )
            )
        _record_task(
            db, run.id, "buyer_matching",
            {"listing_id": listing.id, "active_requirements": len(requirements)},
            {"matches": [item.model_dump() for item in matches]},
        )

        next_action = (
            "Manual identity and listing review is required before publication or buyer contact."
        )
        response = WorkflowResponse(
            workflow_run_id=run.id,
            listing_id=listing.id,
            workflow_status="completed",
            listing_status=listing.status,
            trust=trust,
            matches=matches,
            next_action=next_action,
        )
        result = response.model_dump(mode="json")
        run.status = "completed"
        run.result_json = result
        run.completed_at = datetime.now(UTC)
        _record_task(
            db, run.id, "orchestrator",
            {"workflow_run_id": run.id},
            {"status": run.status, "next_action": next_action},
        )
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise
