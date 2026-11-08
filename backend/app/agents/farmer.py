from app.agents.schemas import ProduceOfferInput


def structure_offer(payload: ProduceOfferInput) -> dict:
    """Normalize a structured farmer offer; no external facts are inferred."""
    return {
        "crop_name": " ".join(payload.crop_name.lower().split()),
        "quantity": payload.quantity,
        "unit": payload.unit,
        "quality_description": payload.quality_description.strip(),
        "location": " ".join(payload.location.split()),
        "available_on": payload.available_on,
        "asking_price": payload.asking_price,
        "currency": payload.currency,
    }
