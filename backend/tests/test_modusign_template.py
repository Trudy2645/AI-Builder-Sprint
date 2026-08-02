import base64
import json

import httpx
import pytest

from app.integrations.modusign import (
    ModusignClient,
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
