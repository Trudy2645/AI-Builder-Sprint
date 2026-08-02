from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai.schemas import BoundingBox, DocumentParseResult, ParsedBlock, ParsedPage
from app.api.dependencies import get_contract_service, get_modusign_client, get_storage_provider
from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.domain.contracts.service import ContractService
from app.domain.contracts.signature_fields import signature_field_candidates
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
)

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


def test_source_pdf_fields_use_distinct_anchors_for_a_single_ocr_table_block() -> None:
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

    fields = signature_field_candidates(parsed)
    by_label = {field["data_label"]: field for field in fields}

    assert by_label["buyer_name"]["position"]["page"] == 1
    assert (
        by_label["buyer_name"]["position"]["y"]
        != by_label["buyer_passport_or_nationality"]["position"]["y"]
    )
    assert by_label["buyer_signature"]["field_type"] == "SIGNATURE"
    assert by_label["buyer_phone"]["position"]["y"] != by_label["buyer_email"]["position"]["y"] or (
        by_label["buyer_phone"]["position"]["x"] != by_label["buyer_email"]["position"]["x"]
    )


def test_source_pdf_text_fields_include_required_modusign_text_style() -> None:
    fields = ContractService._source_pdf_fields(
        [
            {
                "data_label": "buyer_name",
                "field_type": "TEXT",
                "position": {"page": 1, "x": 0.2, "y": 0.3},
                "size": {"width": 0.3, "height": 0.04},
            }
        ],
        1,
    )

    assert fields[0].as_payload()["textStyle"] == {
        "size": 12,
        "font": "NOTO_SANS",
        "align": "LEFT",
    }


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
