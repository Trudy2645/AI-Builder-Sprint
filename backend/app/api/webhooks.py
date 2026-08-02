import hmac
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_contract_service, get_modusign_client, get_storage_provider
from app.core.config import Settings, get_settings
from app.core.database import get_database_session
from app.core.errors import AppError
from app.domain.contracts.service import ContractService
from app.integrations.modusign import ModusignClient
from app.integrations.storage import StorageProvider

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/modusign", status_code=status.HTTP_202_ACCEPTED)
async def receive_modusign_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[ContractService, Depends(get_contract_service)],
    client: Annotated[ModusignClient, Depends(get_modusign_client)],
    storage: Annotated[StorageProvider, Depends(get_storage_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
    signature: Annotated[str | None, Header(alias="X-Modusign-Signature")] = None,
    webhook_token: Annotated[str | None, Header(alias="X-BusanLink-Webhook-Token")] = None,
) -> dict[str, bool]:
    webhook_secret = settings.effective_modusign_webhook_secret
    if not webhook_secret:
        raise AppError(
            status_code=503,
            code="MODUSIGN_WEBHOOK_NOT_CONFIGURED",
            message="Webhook secret is not configured.",
        )
    # Modusign webhooks do not generate an HMAC signature themselves.  The
    # workspace webhook configuration sends the headers configured by the
    # requester, so authenticate that fixed secret directly.  The legacy
    # header is accepted for existing installations during the transition.
    supplied = webhook_token or signature or ""
    if not hmac.compare_digest(webhook_secret, supplied):
        raise AppError(
            status_code=401, code="INVALID_WEBHOOK_SIGNATURE", message="Invalid webhook signature."
        )
    try:
        payload: dict[str, Any] = await request.json()
    except ValueError as exc:
        raise AppError(
            status_code=400, code="INVALID_WEBHOOK_PAYLOAD", message="Invalid JSON payload."
        ) from exc
    event_id = payload.get("id") or payload.get("eventId")
    document = payload.get("document") or payload.get("data") or {}
    document_id = document.get("id") or payload.get("documentId")
    if not isinstance(event_id, str) or not isinstance(document_id, str):
        raise AppError(
            status_code=400,
            code="INVALID_WEBHOOK_PAYLOAD",
            message="Event and document identifiers are required.",
        )
    result = await session.execute(
        text(
            """insert into public.modusign_webhook_events (provider_event_id, provider_document_id)
                values (:event_id, :document_id)
                on conflict (provider_event_id) do nothing returning id"""
        ),
        {"event_id": event_id, "document_id": document_id},
    )
    inserted = result.scalar_one_or_none()
    await session.commit()
    if inserted is None:
        return {"accepted": True, "duplicate": True}
    try:
        await service.sync_signature_request_from_provider_document(document_id, client, storage)
        await session.execute(
            text(
                "update public.modusign_webhook_events set status='processed', "
                "processed_at=timezone('utc', now()) where id=:id"
            ),
            {"id": inserted},
        )
        await session.commit()
    except Exception:
        await session.execute(
            text("update public.modusign_webhook_events set status='failed' where id=:id"),
            {"id": inserted},
        )
        await session.commit()
        raise
    return {"accepted": True, "duplicate": False}
