from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai.schemas import BoundingBox, DocumentParseResult, ParsedBlock, ParsedPage
from app.api.dependencies import get_contract_service, get_modusign_client, get_storage_provider
from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.domain.contracts.service import ContractService
from app.domain.contracts.signature_fields import (
    SignatureFieldPositionError,
    signature_field_candidates,
)
from app.domain.pricing.service import PriceCalculator
from app.integrations.auth import AuthenticatedUser
from app.integrations.exchange_rates import FakeExchangeRateProvider
from app.integrations.modusign import ModusignParticipant, ModusignUnavailableError
from app.integrations.storage import FakeStorageProvider
from app.repositories.contracts import (
    ContractStateConflictError,
    ContractVersionApprovalContextRecord,
    ContractVersionConflictError,
    SignatureRequestRecord,
    SqlAlchemyContractRepository,
)
from app.schemas.contracts import ContractSignatureRequestCreate

CONTRACT_ID = UUID("b1000000-0000-0000-0000-000000000001")
VERSION_ID = UUID("b2000000-0000-0000-0000-000000000001")
BUYER_ID = UUID("b3000000-0000-0000-0000-000000000001")
SELLER_ID = UUID("b3000000-0000-0000-0000-000000000002")
ORGANIZATION_ID = UUID("b4000000-0000-0000-0000-000000000001")


class FakeSignatureRepository:
    def __init__(self) -> None:
        self.context = ContractVersionApprovalContextRecord(
            contract_id=CONTRACT_ID,
            contract_version_id=VERSION_ID,
            version_no=1,
            buyer_user_id=BUYER_ID,
            seller_organization_id=ORGANIZATION_ID,
            contract_status="signing",
            current_version_id=VERSION_ID,
        )
        self.requests: dict[str, SignatureRequestRecord] = {}
        self.all_approved = True

    async def get_contract_version_approval_context(self, contract_id: UUID, version_id: UUID):
        return self.context if (contract_id, version_id) == (CONTRACT_ID, VERSION_ID) else None

    async def is_seller_member(self, user_id: UUID, organization_id: UUID) -> bool:
        return (user_id, organization_id) == (SELLER_ID, ORGANIZATION_ID)

    async def begin_signature_request(self, **kwargs):
        if self.context.current_version_id != kwargs["contract_version_id"]:
            raise ContractVersionConflictError
        if self.context.contract_status != "signing" or not self.all_approved:
            raise ContractStateConflictError
        existing = self.requests.get(kwargs["idempotency_key"])
        if existing:
            return replace(existing, reused=True)
        record = SignatureRequestRecord(
            id=uuid4(),
            contract_id=kwargs["contract_id"],
            contract_version_id=kwargs["contract_version_id"],
            status="preparing",
            provider="modusign",
            provider_document_id=None,
            provider_status=None,
            current_signing_order=None,
            completed_at=None,
        )
        self.requests[kwargs["idempotency_key"]] = record
        return record

    async def mark_signature_request_dispatched(
        self, request_id: UUID, document_id: str, status: str
    ):
        for key, record in self.requests.items():
            if record.id == request_id:
                updated = replace(
                    record,
                    status="in_progress",
                    provider_document_id=document_id,
                    provider_status=status,
                    current_signing_order=1,
                )
                self.requests[key] = updated
                return updated
        raise AssertionError("unknown request")

    async def mark_signature_request_failed(self, request_id: UUID) -> None:
        return None

    async def get_signature_request(self, request_id: UUID):
        for record in self.requests.values():
            if record.id == request_id:
                return record
        return None

    async def update_signature_request_status(
        self, request_id: UUID, *, provider_status: str, current_signing_order: int | None
    ):
        for key, record in self.requests.items():
            if record.id == request_id:
                updated = replace(
                    record,
                    provider_status=provider_status,
                    current_signing_order=current_signing_order,
                )
                self.requests[key] = updated
                return updated
        raise AssertionError("unknown request")

    async def complete_signature_request(self, request_id: UUID, **_kwargs):
        for key, record in self.requests.items():
            if record.id == request_id:
                updated = replace(record, status="completed", provider_status="COMPLETED")
                self.requests[key] = updated
                return updated
        raise AssertionError("unknown request")


class FakeModusignClient:
    def __init__(self) -> None:
        self.calls = 0
        self.unavailable = False
        self.completed = False

    async def create_signature_request(
        self, *, template_id: str, title: str, participants: list[ModusignParticipant]
    ) -> dict[str, str]:
        self.calls += 1
        if self.unavailable:
            raise ModusignUnavailableError
        assert template_id == "template-1"
        assert len(participants) == 1
        assert participants[0].role == "바이어"
        assert participants[0].email == "buyer@example.test"
        return {"id": "modusign-doc-1", "status": "ON_PROCESSING"}

    async def get_document(self, document_id: str) -> dict[str, object]:
        assert document_id == "modusign-doc-1"
        if self.completed:
            return {
                "id": document_id,
                "status": "COMPLETED",
                "file": {"downloadUrl": "https://files.test/signed"},
                "auditTrail": {"downloadUrl": "https://files.test/audit"},
            }
        return {"id": document_id, "status": "ON_GOING", "currentSigningOrder": 2}

    async def fetch_file(self, url: str) -> tuple[bytes, str]:
        return (b"signed" if url.endswith("signed") else b"audit", "application/pdf")


class EmptyOneMappingResult:
    def mappings(self) -> "EmptyOneMappingResult":
        return self

    def one_or_none(self) -> None:
        return None


class CapturingSession:
    def __init__(self) -> None:
        self.statement: object | None = None
        self.params: dict[str, object] | None = None

    async def execute(self, statement: object, params: dict[str, object]) -> EmptyOneMappingResult:
        self.statement = statement
        self.params = params
        return EmptyOneMappingResult()


@pytest.fixture
def signature_repository() -> FakeSignatureRepository:
    return FakeSignatureRepository()


@pytest.fixture
def signature_client(
    app: FastAPI, signature_repository: FakeSignatureRepository
) -> tuple[TestClient, FakeModusignClient]:
    provider = FakeModusignClient()
    service = ContractService(
        signature_repository,  # type: ignore[arg-type]
        PriceCalculator(FakeExchangeRateProvider()),
    )
    app.dependency_overrides[get_contract_service] = lambda: service
    app.dependency_overrides[get_modusign_client] = lambda: provider
    app.dependency_overrides[get_storage_provider] = lambda: FakeStorageProvider()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=BUYER_ID, email="buyer@example.test"
    )
    app.dependency_overrides[get_settings] = lambda: Settings(modusign_template_id="template-1")
    return TestClient(app), provider


def _payload() -> dict[str, object]:
    return {
        "title": "Busan tour contract",
        "buyer": {"name": "Buyer", "email": "buyer@example.test"},
        "seller": {"name": "Seller", "email": "seller@example.test"},
    }


@pytest.mark.asyncio
async def test_signature_source_prefers_exact_contract_version_pdf() -> None:
    session = CapturingSession()
    repository = SqlAlchemyContractRepository(session)  # type: ignore[arg-type]

    assert await repository.get_signature_source_document(CONTRACT_ID, VERSION_ID) is None

    sql = " ".join(str(session.statement).split())
    assert "d.contract_id = :contract_id" in sql
    assert "d.contract_version_id = :contract_version_id" in sql
    assert "d.purpose = 'draft_pdf'" in sql
    assert "d.status = 'ready'" in sql
    assert "c.initial_request_kind = 'as_is'" in sql
    assert "order by d.priority, d.created_at desc" in sql


def test_text_pdf_uses_unique_modusign_signature_anchor() -> None:
    fields = ContractService._source_pdf_fields(
        candidates=[],
        page_count=2,
        page_texts=["계약 내용", "바이어 서명"],
    )

    assert len(fields) == 1
    assert fields[0].as_payload() == {
        "type": "SIGNATURE",
        "dataLabel": "buyer_signature",
        "required": True,
        "position": {
            "anchor": {
                "text": "바이어 서명",
                "offset": {"x": 0.01, "y": 0.005},
            }
        },
        "size": {"width": 0.15, "height": 0.05},
        "signatureTypes": ["SIGN"],
    }


def test_table_level_ocr_bbox_is_not_used_as_a_signature_coordinate() -> None:
    parsed = DocumentParseResult(
        pages=[
            ParsedPage(
                page_number=1,
                blocks=[
                    ParsedBlock(
                        block_id="buyer-table",
                        block_type="table",
                        content=(
                            "바이어 (예약자)\n성명/단체명: ______\n"
                            "국적·여권번호(외국인): ______\n"
                            "연락처: ______ | 이메일: ______\n"
                            "계약 체결일\n이용 기간\n이용 인원\n바이어 서명"
                        ),
                        page_number=1,
                        bbox=BoundingBox(x=0.1, y=0.2, width=0.8, height=0.5),
                    )
                ],
            )
        ]
    )

    assert signature_field_candidates(parsed) == []
    with pytest.raises(SignatureFieldPositionError):
        ContractService._source_pdf_fields([], 1, [])


def test_isolated_ocr_marker_uses_its_real_bbox() -> None:
    parsed = DocumentParseResult(
        pages=[
            ParsedPage(
                page_number=2,
                blocks=[
                    ParsedBlock(
                        block_id="buyer-signature-label",
                        block_type="paragraph",
                        content="바이어 서명 (인)",
                        page_number=2,
                        bbox=BoundingBox(x=0.50, y=0.80, width=0.12, height=0.03),
                    )
                ],
            )
        ]
    )

    candidates = signature_field_candidates(parsed)
    fields = ContractService._source_pdf_fields(candidates, 2, [])

    assert candidates[0]["placement_strategy"] == "ocr_marker_bbox"
    assert fields[0].position == {"page": 2, "x": pytest.approx(0.63), "y": 0.785}
    assert fields[0].size == {"width": 0.20, "height": 0.06}


def test_manual_coordinate_is_validated_and_used() -> None:
    fields = ContractService._source_pdf_fields(
        [
            {
                "data_label": "buyer_signature",
                "field_type": "SIGNATURE",
                "position": {"page": 2, "x": 0.55, "y": 0.75},
                "size": {"width": 0.20, "height": 0.06},
                "placement_strategy": "manual_coordinate",
            }
        ],
        2,
        [],
    )

    assert fields[0].position == {"page": 2, "x": 0.55, "y": 0.75}


def test_legacy_guessed_or_out_of_bounds_coordinate_is_rejected() -> None:
    candidates = [
        {
            "data_label": "buyer_signature",
            "field_type": "SIGNATURE",
            "position": {"page": 1, "x": 0.94, "y": 0.64},
            "size": {"width": 0.04, "height": 0.06},
        },
        {
            "data_label": "buyer_signature",
            "field_type": "SIGNATURE",
            "position": {"page": 1, "x": 0.90, "y": 0.64},
            "size": {"width": 0.20, "height": 0.06},
            "placement_strategy": "manual_coordinate",
        },
    ]

    with pytest.raises(SignatureFieldPositionError):
        ContractService._source_pdf_fields(candidates, 1, [])


@pytest.mark.asyncio
async def test_source_pdf_without_trustworthy_position_fails_before_request_is_persisted(
    signature_repository: FakeSignatureRepository,
) -> None:
    service = ContractService(
        signature_repository,  # type: ignore[arg-type]
        PriceCalculator(FakeExchangeRateProvider()),
    )
    provider = FakeModusignClient()

    with pytest.raises(AppError) as error:
        await service.create_signature_request(
            CONTRACT_ID,
            VERSION_ID,
            ContractSignatureRequestCreate.model_validate(_payload()),
            AuthenticatedUser(id=BUYER_ID, email="buyer@example.test"),
            None,
            "missing-position",
            provider,  # type: ignore[arg-type]
            "template-1",
            source_pdf=b"%PDF-1.7\n",
            source_page_count=1,
            source_field_candidates=[],
            source_page_texts=[],
        )

    assert error.value.code == "SIGNATURE_FIELD_POSITION_REQUIRED"
    assert signature_repository.requests == {}
    assert provider.calls == 0


def test_creates_persisted_signature_request(
    signature_client: tuple[TestClient, FakeModusignClient],
) -> None:
    client, provider = signature_client
    response = client.post(
        f"/api/v1/contracts/{CONTRACT_ID}/versions/{VERSION_ID}/signature-requests",
        headers={"Idempotency-Key": "signature-request-1"},
        json=_payload(),
    )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "id": response.json()["data"]["id"],
        "contract_id": str(CONTRACT_ID),
        "contract_version_id": str(VERSION_ID),
        "status": "in_progress",
        "provider": "modusign",
        "provider_document_id": "modusign-doc-1",
        "provider_status": "ON_PROCESSING",
        "current_signing_order": 1,
        "completed_at": None,
        "signed_document_id": None,
        "audit_trail_document_id": None,
        "signing_delivery": "email",
        "reused": False,
    }
    assert provider.calls == 1


def test_idempotency_reuses_persisted_request_without_second_provider_call(
    signature_client: tuple[TestClient, FakeModusignClient],
) -> None:
    client, provider = signature_client
    url = f"/api/v1/contracts/{CONTRACT_ID}/versions/{VERSION_ID}/signature-requests"
    headers = {"Idempotency-Key": "signature-request-1"}

    first = client.post(url, headers=headers, json=_payload())
    second = client.post(url, headers=headers, json=_payload())

    assert first.status_code == second.status_code == 200
    assert second.json()["data"]["reused"] is True
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert provider.calls == 1


def test_requires_both_approvals_before_calling_provider(
    signature_client: tuple[TestClient, FakeModusignClient],
    signature_repository: FakeSignatureRepository,
) -> None:
    client, provider = signature_client
    signature_repository.all_approved = False
    response = client.post(
        f"/api/v1/contracts/{CONTRACT_ID}/versions/{VERSION_ID}/signature-requests",
        headers={"Idempotency-Key": "signature-request-1"},
        json=_payload(),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SIGNATURE_NOT_READY"
    assert provider.calls == 0


def test_sync_refreshes_provider_status(
    signature_client: tuple[TestClient, FakeModusignClient],
) -> None:
    client, _provider = signature_client
    created = client.post(
        f"/api/v1/contracts/{CONTRACT_ID}/versions/{VERSION_ID}/signature-requests",
        headers={"Idempotency-Key": "signature-request-1"},
        json=_payload(),
    )

    response = client.post(f"/api/v1/signature-requests/{created.json()['data']['id']}/sync")

    assert response.status_code == 200
    assert response.json()["data"]["provider_status"] == "ON_GOING"
    assert response.json()["data"]["current_signing_order"] == 2


def test_sync_completion_stores_artifacts_before_marking_completed(
    signature_client: tuple[TestClient, FakeModusignClient],
) -> None:
    client, provider = signature_client
    created = client.post(
        f"/api/v1/contracts/{CONTRACT_ID}/versions/{VERSION_ID}/signature-requests",
        headers={"Idempotency-Key": "signature-request-1"},
        json=_payload(),
    )
    provider.completed = True

    response = client.post(f"/api/v1/signature-requests/{created.json()['data']['id']}/sync")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "completed"
