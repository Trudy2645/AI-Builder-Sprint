from uuid import UUID, uuid4

import pytest

from app.core.errors import AppError
from app.domain.modusign.service import ModusignService
from app.integrations.auth import AuthenticatedUser
from app.integrations.storage import FakeStorageProvider
from app.repositories.document_processing import (
    ProcessingDocumentRecord,
    ProcessingMembershipRecord,
)
from app.schemas.modusign import SignatureRequestFromDocumentCreate


class Repo:
    def __init__(
        self, record: ProcessingDocumentRecord, membership: ProcessingMembershipRecord | None
    ):
        self.record = record
        self.membership = membership

    async def get_document(self, document_id: UUID):
        return self.record if document_id == self.record.id else None

    async def get_membership(self, user_id: UUID, organization_id: UUID):
        return self.membership


class Client:
    async def create_signature_request_from_pdf(self, **kwargs):
        assert kwargs["pdf_bytes"].startswith(b"%PDF")
        assert kwargs["buyer"].email == "buyer@example.com"
        return {"id": "modu-1", "title": kwargs["title"], "status": "ON_PROCESSING"}


@pytest.mark.asyncio
async def test_create_from_document_reads_original_and_sends_buyer_fields():
    document_id = uuid4()
    organization_id = uuid4()
    record = ProcessingDocumentRecord(
        id=document_id,
        listing_id=None,
        contract_id=None,
        purpose="source_contract",
        status="uploaded",
        storage_bucket="contracts",
        storage_object_path="source.pdf",
        original_filename="source.pdf",
        mime_type="application/pdf",
        size_bytes=8,
        content_sha256=None,
        failure_code=None,
        extracted_data={},
        uploaded_by=None,
        seller_organization_id=organization_id,
        listing_title="숙박",
        listing_category="accommodation",
        listing_language="ko-KR",
    )
    storage = FakeStorageProvider()
    storage.objects[("contracts", "source.pdf")] = b"%PDF-1.7\n"
    service = ModusignService(
        Repo(record, ProcessingMembershipRecord(organization_id, "seller")), storage, Client()
    )
    payload = SignatureRequestFromDocumentCreate(
        document_id=str(document_id),
        title="숙박 계약",
        buyer={"role": "바이어", "name": "Buyer", "email": "buyer@example.com"},
        fields=[
            {
                "field_type": "SIGNATURE",
                "data_label": "buyer_signature",
                "position": {"anchor": {"text": "바이어 서명"}},
            }
        ],
    )
    result = await service.create_from_document(
        payload, AuthenticatedUser(uuid4(), "buyer@example.com"), str(organization_id)
    )
    assert result.document_id == "modu-1"


@pytest.mark.asyncio
async def test_create_from_document_rejects_wrong_organization():
    organization_id = uuid4()
    record = ProcessingDocumentRecord(
        id=uuid4(),
        listing_id=None,
        contract_id=None,
        purpose="source_contract",
        status="uploaded",
        storage_bucket="contracts",
        storage_object_path="source.pdf",
        original_filename="source.pdf",
        mime_type="application/pdf",
        size_bytes=8,
        content_sha256=None,
        failure_code=None,
        extracted_data={},
        uploaded_by=None,
        seller_organization_id=organization_id,
        listing_title=None,
        listing_category=None,
        listing_language=None,
    )
    service = ModusignService(Repo(record, None), FakeStorageProvider(), Client())
    payload = SignatureRequestFromDocumentCreate(
        document_id=str(record.id),
        title="숙박 계약",
        buyer={"role": "바이어", "name": "Buyer", "email": "buyer@example.com"},
        fields=[
            {
                "field_type": "SIGNATURE",
                "data_label": "buyer_signature",
                "position": {"page": 1, "x": 0.5, "y": 0.5},
            }
        ],
    )
    with pytest.raises(AppError) as error:
        await service.create_from_document(payload, AuthenticatedUser(uuid4(), None), str(uuid4()))
    assert error.value.code == "DOCUMENT_ACCESS_DENIED"
