import base64
import json

import httpx
import pytest

from app.integrations.modusign import (
    ModusignClient,
    ModusignParticipant,
    ModusignParticipantField,
    build_accommodation_template_payload,
)


def test_accommodation_template_payload_has_one_buyer_signature() -> None:
    payload = build_accommodation_template_payload(
        title="BusanLink 숙박 계약서 v1", pdf_bytes=b"%PDF-1.7\nexample"
    )

    assert payload["file"]["extension"] == "pdf"
    assert base64.b64decode(payload["file"]["base64"]) == b"%PDF-1.7\nexample"
    assert payload["participants"] == [
        {
            "type": "SIGNER",
            "role": "바이어",
            "signingOrder": 1,
            "fields": [
                {
                    "type": "SIGNATURE",
                    "required": True,
                    "dataLabel": "buyer_signature",
                    "position": {"page": 2, "x": 0.56, "y": 0.72},
                    "size": {"width": 0.30, "height": 0.06},
                }
            ],
        }
    ]


def test_accommodation_template_rejects_non_pdf() -> None:
    with pytest.raises(ValueError, match="must be a PDF"):
        build_accommodation_template_payload(title="bad", pdf_bytes=b"not-a-pdf")


@pytest.mark.asyncio
async def test_client_posts_accommodation_template() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["payload"] = json.loads(request.content)
        return httpx.Response(201, json={"id": "template-1"})

    client = ModusignClient(
        base_url="https://modusign.test",
        api_key="test-key",
        auth_email="seller@example.test",
        transport=httpx.MockTransport(handler),
    )
    result = await client.create_accommodation_template(
        title="숙박 계약서", pdf_bytes=b"%PDF-1.7\nexample"
    )

    assert result == {"id": "template-1"}
    assert captured["method"] == "POST"
    assert captured["path"] == "/templates"
    assert captured["payload"] == build_accommodation_template_payload(
        title="숙박 계약서", pdf_bytes=b"%PDF-1.7\nexample"
    )


@pytest.mark.asyncio
async def test_client_sends_original_pdf_with_buyer_fields() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["payload"] = json.loads(request.content)
        return httpx.Response(201, json={"id": "document-1"})

    client = ModusignClient(
        base_url="https://modusign.test",
        api_key="test-key",
        auth_email="seller@example.test",
        transport=httpx.MockTransport(handler),
    )
    result = await client.create_signature_request_from_pdf(
        title="원문 숙박 계약서",
        pdf_bytes=b"%PDF-1.7\nsource",
        buyer=ModusignParticipant("바이어", "Aiko", "aiko@example.test"),
        buyer_fields=[
            ModusignParticipantField(
                field_type="SIGNATURE",
                data_label="buyer_signature",
                position={"anchor": {"text": "바이어 서명"}},
                size={"width": 0.3, "height": 0.06},
                signature_types=["SIGN"],
            ),
            ModusignParticipantField(
                field_type="TEXT",
                data_label="buyer_group_name",
                position={"x": 0.2, "y": 0.7, "page": 2},
                size={"width": 0.3, "height": 0.04},
                required=False,
            ),
            ModusignParticipantField(
                field_type="SIGNING_DATE",
                data_label="buyer_signed_at",
                position={"x": 0.55, "y": 0.75, "page": 2},
                size={"width": 0.14, "height": 0.035},
            ),
        ],
    )

    assert result == {"id": "document-1"}
    assert captured["path"] == "/documents"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["participants"][0]["fields"][0]["dataLabel"] == "buyer_signature"
    assert payload["participants"][0]["fields"][0]["signatureTypes"] == ["SIGN"]
    assert payload["participants"][0]["fields"][1]["required"] is False
    assert payload["participants"][0]["fields"][2]["type"] == "SIGNING_DATE"
    assert payload["participants"][0]["fields"][2]["displayFormat"] == "YYYY년 MM월 DD일"
