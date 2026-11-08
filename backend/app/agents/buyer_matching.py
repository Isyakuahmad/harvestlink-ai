from app.agents.schemas import MatchResult


CROP_ALIASES = {"corn": "maize", "maize": "maize", "paddy rice": "rice"}


def _crop(value: str) -> str:
    normalized = " ".join(value.lower().split())
    return CROP_ALIASES.get(normalized, normalized)


def _kg(quantity: float, unit: str) -> float:
    if unit == "kg":
        return quantity
    if unit == "tonne":
        return quantity * 1000
    raise ValueError(f"Unsupported unit: {unit}")


def _same_area(left: str, right: str) -> bool:
    left_parts = {part.strip().lower() for part in left.split(",") if part.strip()}
    right_parts = {part.strip().lower() for part in right.split(",") if part.strip()}
    return bool(left_parts & right_parts)


def rank_requirement(offer: dict, requirement) -> MatchResult:
    reasons: list[str] = []
    if _crop(offer["crop_name"]) != _crop(requirement.crop_name):
        return MatchResult(
            buyer_requirement_id=requirement.id,
            score=0,
            eligible=False,
            reasons=["Crop does not match the buyer requirement"],
        )

    offer_kg = _kg(offer["quantity"], offer["unit"])
    minimum_kg = _kg(requirement.min_quantity, requirement.unit)
    maximum_kg = (
        _kg(requirement.max_quantity, requirement.unit)
        if requirement.max_quantity is not None
        else None
    )
    if offer_kg < minimum_kg or (maximum_kg is not None and offer_kg > maximum_kg):
        return MatchResult(
            buyer_requirement_id=requirement.id,
            score=0,
            eligible=False,
            reasons=["Offered quantity is outside the buyer's stated range"],
        )

    score = 30.0
    reasons.append("Crop matches")
    score += 20
    reasons.append("Quantity is within the buyer's stated range")

    if _same_area(offer["location"], requirement.location):
        score += 20
        reasons.append("Location shares a stated area or region")
    else:
        reasons.append("Location compatibility needs human confirmation")

    required_quality = requirement.quality_requirements.lower().strip()
    offered_quality = offer["quality_description"].lower()
    if not required_quality:
        score += 20
        reasons.append("Buyer has not specified additional quality criteria")
    elif all(term in offered_quality for term in required_quality.split() if len(term) > 3):
        score += 20
        reasons.append("Offer description contains the buyer's quality terms")
    else:
        reasons.append("Quality requirements need manual confirmation")

    asking_price = offer.get("asking_price")
    if (
        asking_price is not None
        and requirement.max_price is not None
        and offer.get("currency")
        and offer.get("currency") == requirement.currency
    ):
        if asking_price <= requirement.max_price:
            score += 10
            reasons.append("Asking price is within the buyer's stated limit")
        else:
            return MatchResult(
                buyer_requirement_id=requirement.id,
                score=0,
                eligible=False,
                reasons=["Asking price exceeds the buyer's stated limit"],
            )
    else:
        reasons.append("Price compatibility is unknown or not comparable")

    return MatchResult(
        buyer_requirement_id=requirement.id,
        score=round(score, 2),
        eligible=True,
        reasons=reasons,
    )


def find_matches(offer: dict, requirements: list) -> list[MatchResult]:
    results = [rank_requirement(offer, item) for item in requirements]
    return sorted(results, key=lambda item: (item.eligible, item.score), reverse=True)
