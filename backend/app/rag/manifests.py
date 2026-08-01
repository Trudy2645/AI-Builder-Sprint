from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError, model_validator

ContractCategory = Literal["vehicle_rental", "activity", "tour", "accommodation"]
KnowledgeCorpus = Literal["official_evidence", "approved_templates", "case_reference"]


class KnowledgeManifestError(ValueError):
    pass


class KnowledgeManifestEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_key: str = Field(pattern=r"^[A-Za-z0-9가-힣_-]+$", max_length=200)
    title: str = Field(min_length=1, max_length=500)
    corpus: KnowledgeCorpus
    source_type: str = Field(min_length=1, max_length=100)
    authority: str | None = Field(default=None, max_length=300)
    source_url: HttpUrl | None = None
    contract_categories: list[ContractCategory] = Field(min_length=1, max_length=4)
    activity_subtypes: list[str] = Field(default_factory=list, max_length=8)
    party_type: str = Field(default="B2C_individual", min_length=1, max_length=100)
    effective_from: date | None = None
    effective_to: date | None = None
    retrieved_at: datetime
    version_label: str = Field(min_length=1, max_length=100)
    status: Literal["reviewed", "approved"]
    approved_by: str = Field(min_length=1, max_length=200)
    approved_at: datetime
    local_path: str = Field(min_length=1, max_length=1000)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_count: int = Field(gt=0)
    file_size: int = Field(gt=0)
    applicability_note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_scope(self) -> KnowledgeManifestEntry:
        if self.effective_from and self.effective_to and self.effective_from > self.effective_to:
            raise ValueError("effective_from must not be after effective_to")
        if self.corpus == "official_evidence" and self.status != "reviewed":
            raise ValueError("official evidence must be reviewed")
        if self.corpus != "official_evidence" and self.status != "approved":
            raise ValueError("templates and cases must be approved")
        if "activity" in self.contract_categories and self.activity_subtypes:
            if any(not item.strip() for item in self.activity_subtypes):
                raise ValueError("activity_subtypes must not be blank")
        return self

    def resolve_local_file(self, source_root: Path) -> Path:
        root = source_root.resolve()
        relative = Path(self.local_path)
        if relative.parts and relative.parts[0] == "rag":
            relative = Path(*relative.parts[1:])
        expected_prefix = {
            "official_evidence": Path("data/official"),
            "approved_templates": Path("data/templates"),
            "case_reference": Path("data/case_reference"),
        }[self.corpus]
        try:
            relative.relative_to(expected_prefix)
        except ValueError as exc:
            raise KnowledgeManifestError(
                "knowledge path does not match its isolated corpus"
            ) from exc
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise KnowledgeManifestError("local_path escapes source root") from exc
        if not candidate.is_file():
            raise KnowledgeManifestError(f"knowledge file not found: {relative}")
        return candidate

    def verified_content(self, source_root: Path) -> bytes:
        path = self.resolve_local_file(source_root)
        content = path.read_bytes()
        if len(content) != self.file_size:
            raise KnowledgeManifestError(f"file size mismatch for {self.source_key}")
        if hashlib.sha256(content).hexdigest() != self.content_sha256:
            raise KnowledgeManifestError(f"sha256 mismatch for {self.source_key}")
        if not content.startswith(b"%PDF-"):
            raise KnowledgeManifestError(
                f"only reviewed PDF files may be ingested: {self.source_key}"
            )
        return content

    def provider_attributes(self, document_version_id: str) -> dict[str, str | int | bool]:
        end = self.effective_to or date(9999, 12, 31)
        start = self.effective_from or date(1, 1, 1)
        values: dict[str, str | int | bool] = {
            "corpus": self.corpus,
            "status": "active",
            "party_type": self.party_type,
            "source_key": self.source_key,
            "document_version_id": document_version_id,
            "content_sha256": self.content_sha256,
            "effective_from_epoch": _date_epoch(start),
            "effective_to_epoch": _date_epoch(end),
        }
        for category in ("common", "vehicle_rental", "activity", "tour", "accommodation"):
            values[f"category_{category}"] = (
                False if category == "common" else category in self.contract_categories
            )
        values["activity_subtype"] = (
            self.activity_subtypes[0] if self.activity_subtypes else "common"
        )
        if len(values) > 16:
            raise KnowledgeManifestError("provider attributes exceed the 16-field limit")
        return values


def load_knowledge_manifest(path: Path, corpus: KnowledgeCorpus) -> list[KnowledgeManifestEntry]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_sources = payload["sources"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise KnowledgeManifestError(f"invalid manifest: {path}") from exc
    if not isinstance(raw_sources, list):
        raise KnowledgeManifestError("manifest sources must be a list")
    retrieved = payload.get("retrieved_at") or payload.get("retrieved_date")
    entries: list[KnowledgeManifestEntry] = []
    for raw in raw_sources:
        try:
            entries.append(
                KnowledgeManifestEntry.model_validate(_canonical_entry(raw, corpus, retrieved))
            )
        except ValidationError as exc:
            source_key = raw.get("source_key") if isinstance(raw, dict) else "unknown"
            raise KnowledgeManifestError(
                f"manifest source is not approved or valid: {source_key}"
            ) from exc
    if len({item.source_key for item in entries}) != len(entries):
        raise KnowledgeManifestError("manifest source_key values must be unique")
    return entries


def _canonical_entry(
    raw: dict[str, Any], corpus: KnowledgeCorpus, retrieved: Any
) -> dict[str, Any]:
    approved_at = raw.get("approved_at")
    effective_from = raw.get("effective_from") or raw.get("decision_date")
    version = raw.get("version") or effective_from or raw.get("content_sha256", "")[:12]
    title = raw.get("title") or " ".join(
        item for item in (raw.get("court"), raw.get("case_number"), raw.get("case_name")) if item
    )
    party_type = raw.get("party_type") or (
        "B2B_reference" if "B2B" in str(raw.get("scope_note", "")) else "B2C_individual"
    )
    authority = raw.get("authority") or raw.get("court")
    source_url = raw.get("source_page_url") or raw.get("official_source_url")
    status = raw.get("status")
    if corpus == "official_evidence" and status == "downloaded":
        status = "downloaded"
    return {
        "source_key": raw.get("source_key"),
        "title": title,
        "corpus": corpus,
        "source_type": raw.get("source_type"),
        "authority": authority,
        "source_url": source_url,
        "contract_categories": raw.get("contract_categories"),
        "activity_subtypes": raw.get("activity_subtypes") or [],
        "party_type": party_type,
        "effective_from": effective_from,
        "effective_to": raw.get("effective_to"),
        "retrieved_at": retrieved or approved_at,
        "version_label": str(version),
        "status": status,
        "approved_by": raw.get("approved_by"),
        "approved_at": approved_at,
        "local_path": raw.get("local_path"),
        "content_sha256": raw.get("content_sha256"),
        "page_count": raw.get("page_count"),
        "file_size": raw.get("file_size"),
        "applicability_note": raw.get("applicability_note") or raw.get("scope_note"),
    }


def _date_epoch(value: date) -> int:
    return int(datetime(value.year, value.month, value.day, tzinfo=UTC).timestamp())


__all__ = [
    "KnowledgeCorpus",
    "KnowledgeManifestEntry",
    "KnowledgeManifestError",
    "load_knowledge_manifest",
]
