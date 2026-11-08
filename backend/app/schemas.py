from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=10, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    verification_status: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class BuyerRegister(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=10, max_length=128)
    organization_name: str = Field(min_length=2, max_length=180)
    buyer_type: str = Field(min_length=2, max_length=40)
    phone: str = Field(min_length=7, max_length=30)
    location: str = Field(min_length=2, max_length=180)


class VerificationDecision(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    reason: str = Field(min_length=5, max_length=1000)


class FarmProfileCreate(BaseModel):
    farm_name: str = Field(min_length=2, max_length=160)
    location: str = Field(min_length=2, max_length=180)
    acreage: float = Field(gt=0, le=100000)
    acreage_unit: str = Field(default="hectare", pattern="^(hectare|acre)$")
    land_access: str = Field(pattern="^(owned|leased|family|community|other)$")


class FarmSeasonCreate(BaseModel):
    farm_profile_id: int = Field(gt=0)
    crop_name: str = Field(min_length=2, max_length=100)
    season_name: str = Field(min_length=2, max_length=100)
    planted_area: float = Field(gt=0, le=100000)
    area_unit: str = Field(default="hectare", pattern="^(hectare|acre)$")
    planting_date: str | None = None
    expected_harvest_date: str | None = None


class FarmActivityCreate(BaseModel):
    season_id: int = Field(gt=0)
    activity_type: str = Field(pattern="^(land_preparation|planting|input_purchase|fertilising|pest_control|irrigation|labour|observation|harvest|sale|delivery|other)$")
    description: str = Field(min_length=3, max_length=2000)
    activity_date: str
    quantity: float | None = Field(default=None, ge=0)
    quantity_unit: str | None = Field(default=None, max_length=30)
    amount: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    source_channel: str = Field(default="web", pattern="^(web|whatsapp|voice|admin)$")


class FarmEvidenceCreate(BaseModel):
    evidence_type: str = Field(pattern="^(receipt|invoice|photo|delivery_note|buyer_confirmation|other)$")
    evidence_uri: str = Field(min_length=8, max_length=2000)
    description: str = Field(default="", max_length=500)


class FarmShareCreate(BaseModel):
    season_id: int | None = Field(default=None, gt=0)
    recipient_name: str = Field(min_length=2, max_length=160)
    recipient_type: str = Field(pattern="^(bank|microfinance|government_programme|cooperative|grant_provider|other)$")
    purpose: str = Field(min_length=5, max_length=300)
    expires_in_days: int = Field(default=14, ge=1, le=90)
