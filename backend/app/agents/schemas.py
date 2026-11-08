from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProduceOfferInput(BaseModel):
    crop_name: str = Field(min_length=2, max_length=100)
    quantity: float = Field(gt=0, le=10_000_000)
    unit: str
    quality_description: str = Field(min_length=3, max_length=2000)
    location: str = Field(min_length=2, max_length=180)
    available_on: date
    asking_price: float | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)

    @field_validator("unit")
    @classmethod
    def normalize_unit(cls, value: str) -> str:
        normalized = value.strip().lower()
        aliases = {"ton": "tonne", "tons": "tonne", "tonnes": "tonne", "kg": "kg", "kgs": "kg"}
        normalized = aliases.get(normalized, normalized)
        if normalized not in {"kg", "tonne"}:
            raise ValueError("unit must be kg or tonne in this MVP")
        return normalized

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class BuyerRequirementInput(BaseModel):
    crop_name: str = Field(min_length=2, max_length=100)
    min_quantity: float = Field(gt=0)
    max_quantity: float | None = Field(default=None, gt=0)
    unit: str
    quality_requirements: str = Field(default="", max_length=2000)
    location: str = Field(min_length=2, max_length=180)
    max_price: float | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)

    @field_validator("unit")
    @classmethod
    def normalize_unit(cls, value: str) -> str:
        normalized = value.strip().lower()
        aliases = {"ton": "tonne", "tons": "tonne", "tonnes": "tonne", "kgs": "kg"}
        normalized = aliases.get(normalized, normalized)
        if normalized not in {"kg", "tonne"}:
            raise ValueError("unit must be kg or tonne in this MVP")
        return normalized

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @field_validator("max_quantity")
    @classmethod
    def validate_quantity_range(cls, value: float | None, info):
        minimum = info.data.get("min_quantity")
        if value is not None and minimum is not None and value < minimum:
            raise ValueError("max_quantity cannot be less than min_quantity")
        return value


class TrustAssessment(BaseModel):
    status: str
    identity_status: str
    checks: list[str]
    warnings: list[str]
    can_publish: bool
    can_contact_buyer: bool


class MatchResult(BaseModel):
    buyer_requirement_id: int
    score: float
    eligible: bool
    reasons: list[str]


class WorkflowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workflow_run_id: int
    listing_id: int
    workflow_status: str
    listing_status: str
    trust: TrustAssessment
    matches: list[MatchResult]
    next_action: str
