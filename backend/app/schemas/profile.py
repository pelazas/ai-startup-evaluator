from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProfileBase(BaseModel):
    technical_skills: list[str] = Field(min_length=1)
    domain_expertise: list[str] = Field(min_length=1)
    years_experience: str = Field(min_length=1, max_length=10)
    team_size: str = Field(min_length=1, max_length=20)
    budget_range: str = Field(min_length=1, max_length=20)
    network_strength: int = Field(ge=1, le=10)
    risk_tolerance: str = Field(min_length=1, max_length=10)
    geographic_location: str = Field(min_length=1, max_length=255)

    @field_validator("technical_skills", "domain_expertise")
    @classmethod
    def normalize_string_lists(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item.strip()]
        if not normalized:
            raise ValueError("At least one value is required")
        return normalized

    @field_validator("years_experience", "team_size", "budget_range", "risk_tolerance", "geographic_location")
    @classmethod
    def normalize_strings(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Field cannot be empty")
        return normalized


class ProfileCreate(ProfileBase):
    pass


class ProfileUpdate(ProfileBase):
    pass


class ProfileResponse(ProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str

