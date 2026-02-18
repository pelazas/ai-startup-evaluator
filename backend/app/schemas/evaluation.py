from pydantic import BaseModel, Field, field_validator


class EvaluationCreateRequest(BaseModel):
    idea_description: str = Field(min_length=10)
    target_customer: str | None = None
    problem_statement: str | None = None
    startup_type: str | None = Field(default=None, max_length=50)
    market_type: str | None = Field(default=None, max_length=10)
    web_enabled: bool = True

    @field_validator("idea_description", "target_customer", "problem_statement")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class EvaluationExportRequest(BaseModel):
    chart_image_data_url: str | None = None
    company_name: str | None = Field(default=None, max_length=80)
    company_tagline: str | None = Field(default=None, max_length=160)
    primary_color_hex: str | None = Field(default=None, max_length=7)
    custom_sections: list[dict[str, str]] | None = None
