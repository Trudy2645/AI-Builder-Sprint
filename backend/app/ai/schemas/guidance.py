from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    rejection_reason: str = Field(min_length=1, max_length=4000)


class RevisionGuidanceOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RevisionGuidanceItemOutput] = Field(min_length=1, max_length=50)


class RevisionSuggestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    request_type: Literal["modify", "add"]
    clause_id: str | None = Field(default=None, max_length=100)
    clause_title: str | None = Field(default=None, max_length=500)
    original_text: str | None = Field(default=None, max_length=20_000)
    reason: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_shape(self) -> "RevisionSuggestionRequest":
        clause_values = (self.clause_id, self.clause_title, self.original_text)
        if self.request_type == "modify" and any(value is None for value in clause_values):
            raise ValueError("modify requires the source clause")
        if self.request_type == "add" and any(value is not None for value in clause_values):
            raise ValueError("add must not reference an existing clause")
        return self


class RevisionSuggestionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    suggestion: str = Field(min_length=1, max_length=20_000)


class ChangeSummaryItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=300)
    before: str | None = Field(default=None, max_length=20_000)
    after: str | None = Field(default=None, max_length=20_000)


class ChangeSummaryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changes: list[ChangeSummaryItemInput] = Field(min_length=1, max_length=50)


ContractTranslationLocale = Literal["en-US", "ja-JP", "zh-CN"]


class ContractTranslationClauseInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=20_000)


class ContractTranslationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    target_locale: ContractTranslationLocale
    title: str = Field(min_length=1, max_length=500)
    clauses: list[ContractTranslationClauseInput] = Field(min_length=1, max_length=30)


class ContractTranslationClauseOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=20_000)


class ContractTranslationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    locale: ContractTranslationLocale
    title: str = Field(min_length=1, max_length=500)
    clauses: list[ContractTranslationClauseOutput] = Field(min_length=1, max_length=30)


class ContractAssistantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=500)
    clauses: list[ContractTranslationClauseInput] = Field(min_length=1, max_length=30)


class ContractAssistantFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    clause_id: str = Field(min_length=1, max_length=100)
    severity: Literal["high", "medium", "low"]
    explanation: str = Field(min_length=1, max_length=4000)
    suggested_text: str | None = Field(default=None, max_length=8000)


class ContractAssistantOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[ContractAssistantFinding] = Field(default_factory=list, max_length=30)
