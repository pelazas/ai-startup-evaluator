from pydantic import BaseModel, ConfigDict, Field, field_validator


class AuthRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("Invalid email")
        return normalized


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    has_profile: bool


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserPublic
