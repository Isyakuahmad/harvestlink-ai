from app.agents.schemas import TrustAssessment


def assess_listing(offer: dict, identity_verified: bool = False) -> TrustAssessment:
    checks = ["Required offer fields passed schema validation"]
    warnings: list[str] = []
    if not identity_verified:
        warnings.append("Farmer identity has not yet been independently verified")
    if len(offer["quality_description"]) < 10:
        warnings.append("Quality description is brief and needs manual review")
    if not offer.get("location"):
        warnings.append("Location is missing")

    status = "verified" if identity_verified and not warnings else "review_required"
    return TrustAssessment(
        status=status,
        identity_status="verified" if identity_verified else "unverified",
        checks=checks,
        warnings=warnings,
        can_publish=False,
        can_contact_buyer=False,
    )
