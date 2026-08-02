from pydantic import BaseModel, ConfigDict, Field


class PublicSummaryOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    lines: list[str] = Field(min_length=3, max_length=3)
