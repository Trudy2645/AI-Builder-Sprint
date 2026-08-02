from pydantic import BaseModel, ConfigDict, Field


class RevisionGuidanceItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=100)
    clause_title: str = Field(min_length=1, max_length=300)
    original_text: str = Field(min_length=1, max_length=20_000)
    requested_text: str = Field(min_length=1, max_length=20_000)
    reason: str = Field(min_length=1, max_length=4000)


class RevisionGuidanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RevisionGuidanceItemInput] = Field(min_length=1, max_length=50)


class RevisionGuidanceItemOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str
    impact: str = Field(min_length=1, max_length=4000)
    recommendation: str = Field(min_length=1, max_length=8000)


class RevisionGuidanceOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RevisionGuidanceItemOutput] = Field(min_length=1, max_length=50)


class ChangeSummaryItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=300)
    before: str | None = Field(default=None, max_length=20_000)
    after: str | None = Field(default=None, max_length=20_000)


class ChangeSummaryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changes: list[ChangeSummaryItemInput] = Field(min_length=1, max_length=50)
