from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GeneratedContractClause(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    clause_key: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)


class GeneratedContractDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clauses: list[GeneratedContractClause] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def require_unique_clause_keys(self) -> GeneratedContractDraft:
        keys = [clause.clause_key for clause in self.clauses]
        if len(keys) != len(set(keys)):
            raise ValueError("Generated clause keys must be unique.")
        return self
