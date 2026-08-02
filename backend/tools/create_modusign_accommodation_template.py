"""Create BusanLink's reusable accommodation template in Modusign.

Run from the backend directory after configuring MODUSIGN_API_KEY and
MODUSIGN_AUTH_EMAIL in .env. The command prints the template id to copy into
MODUSIGN_TEMPLATE_ID. It intentionally never prints the API key or PDF content.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.core.config import get_settings
from app.integrations.modusign import ModusignClient, ModusignRequestError

ROOT = Path(__file__).resolve().parents[2]
SOURCE_PDF = ROOT / "frontend/public/samples/accommodation_service_agreement_filled_sample_ko.pdf"


async def main() -> None:
    settings = get_settings()
    if not settings.modusign_api_key or not settings.modusign_auth_email:
        raise SystemExit("Set MODUSIGN_API_KEY and MODUSIGN_AUTH_EMAIL in backend/.env first.")
    if not SOURCE_PDF.is_file():
        raise SystemExit(f"Accommodation PDF not found: {SOURCE_PDF}")

    client = ModusignClient(
        base_url=settings.modusign_base_url,
        api_key=settings.modusign_api_key,
        auth_email=settings.modusign_auth_email,
        timeout_seconds=settings.modusign_timeout_seconds,
    )
    try:
        template = await client.create_accommodation_template(
            title="BusanLink 숙박시설 이용 및 제공 계약서 v1",
            pdf_bytes=SOURCE_PDF.read_bytes(),
        )
    except ModusignRequestError as exc:
        raise SystemExit(
            f"Modusign rejected template creation ({exc.status_code}): {exc.detail[:500]}"
        ) from exc

    template_id = template.get("id")
    if not isinstance(template_id, str) or not template_id:
        raise SystemExit("Modusign did not return a template id.")
    print(f"Created template id: {template_id}")
    print("Set MODUSIGN_TEMPLATE_ID to this value in backend/.env.")


if __name__ == "__main__":
    asyncio.run(main())
