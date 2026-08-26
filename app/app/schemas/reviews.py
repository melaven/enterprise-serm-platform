from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReviewWebhook(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: int = Field(gt=0)
    platform_id: int = Field(gt=0)
    external_review_id: str = Field(min_length=1, max_length=255)
    author_name: str | None = Field(default=None, max_length=255)
    rating: int = Field(ge=1, le=5)
    review_text: str = Field(min_length=1, max_length=20_000)

    @field_validator("external_review_id", "review_text")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @field_validator("author_name")
    @classmethod
    def normalize_author_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None