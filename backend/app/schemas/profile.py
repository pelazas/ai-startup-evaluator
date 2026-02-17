from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProfileBase(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    role_title: str = Field(min_length=1, max_length=40)
    linkedin_url: str | None = Field(default=None, max_length=255)
    location_city_country: str = Field(min_length=1, max_length=255)
    timezone: str = Field(min_length=1, max_length=64)
    current_stage: str = Field(min_length=1, max_length=24)
    industry_focus: list[str] = Field(min_length=1)
    business_model: str = Field(min_length=1, max_length=32)
    target_market: str = Field(min_length=1, max_length=32)
    team_size: str = Field(min_length=1, max_length=20)
    weekly_hours_available: int = Field(ge=1, le=80)
    budget_range: str = Field(min_length=1, max_length=20)
    hiring_ability: str = Field(min_length=1, max_length=16)
    cloud_deployment_level: str = Field(min_length=1, max_length=16)
    ai_coding_agents_level: str = Field(min_length=1, max_length=16)
    backend_engineering_level: str = Field(min_length=1, max_length=16)
    product_ux_level: str = Field(min_length=1, max_length=16)
    data_ml_engineering_level: str = Field(min_length=1, max_length=16)
    shipping_velocity: str = Field(min_length=1, max_length=16)
    domain_expertise_level: int = Field(ge=1, le=5)
    distribution_channels: list[str] = Field(min_length=1)
    audience_access: str = Field(min_length=1, max_length=24)
    sales_experience: str = Field(min_length=1, max_length=16)
    risk_tolerance: str = Field(min_length=1, max_length=10)
    preferred_time_to_revenue: str = Field(min_length=1, max_length=12)
    motivation_type: str = Field(min_length=1, max_length=24)
    commitment_horizon: str = Field(min_length=1, max_length=12)
    regulatory_constraints: bool
    regulatory_constraints_notes: str | None = None
    ip_constraints: bool
    ip_constraints_notes: str | None = None
    geo_legal_constraints: bool
    geo_legal_constraints_notes: str | None = None
    confidence_style: str = Field(min_length=1, max_length=16)
    priority_dimensions: list[str] = Field(min_length=2, max_length=2)

    @field_validator("industry_focus", "distribution_channels", "priority_dimensions")
    @classmethod
    def normalize_string_lists(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item.strip()]
        if not normalized:
            raise ValueError("At least one value is required")
        return normalized

    @field_validator(
        "full_name",
        "role_title",
        "location_city_country",
        "timezone",
        "current_stage",
        "business_model",
        "target_market",
        "team_size",
        "budget_range",
        "hiring_ability",
        "cloud_deployment_level",
        "ai_coding_agents_level",
        "backend_engineering_level",
        "product_ux_level",
        "data_ml_engineering_level",
        "shipping_velocity",
        "audience_access",
        "sales_experience",
        "risk_tolerance",
        "preferred_time_to_revenue",
        "motivation_type",
        "commitment_horizon",
        "confidence_style",
    )
    @classmethod
    def normalize_strings(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Field cannot be empty")
        return normalized

    @field_validator("linkedin_url")
    @classmethod
    def normalize_linkedin_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("regulatory_constraints_notes", "ip_constraints_notes", "geo_legal_constraints_notes")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("priority_dimensions")
    @classmethod
    def validate_priority_dimensions(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("Priority dimensions must be unique")
        return value


class ProfileCreate(ProfileBase):
    pass


class ProfileUpdate(ProfileBase):
    pass


class ProfileResponse(ProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
