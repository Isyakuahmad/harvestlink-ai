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
