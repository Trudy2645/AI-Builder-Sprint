from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.ai.providers.upstage import UpstageAIProvider
from app.core.config import Settings
from app.domain.knowledge.service import KnowledgeIngestionService
from app.integrations.storage import SupabaseStorageProvider
from app.rag.manifests import load_knowledge_manifest
from app.repositories.knowledge import SqlAlchemyKnowledgeRepository


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and ingest reviewed RAG PDF manifests.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument(
        "--corpus",
        choices=("official_evidence", "approved_templates", "case_reference"),
        required=True,
    )
    parser.add_argument("--approved-by", type=UUID, required=True)
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--normalize-provider-pdf", action="store_true")
    parser.add_argument("--provider-text-derivative", action="store_true")
    return parser


async def _run(args: argparse.Namespace) -> None:
    settings = Settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required")
    if not settings.upstage_api_key:
        raise RuntimeError("UPSTAGE_API_KEY is required")
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("Supabase Storage service credentials are required")
    entries = load_knowledge_manifest(args.manifest, args.corpus)
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    provider = UpstageAIProvider(
        api_key=settings.upstage_api_key,
        document_base_url=settings.upstage_document_base_url,
        chat_base_url=settings.upstage_chat_base_url,
        agent_base_url=settings.upstage_agent_base_url,
        chat_model=settings.upstage_chat_model,
        timeout_seconds=settings.ai_request_timeout_seconds,
        max_retries=settings.ai_max_retries,
    )
    storage = SupabaseStorageProvider(
        supabase_url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key,
        timeout_seconds=settings.storage_request_timeout_seconds,
    )
    try:
        async with factory() as session:
            service = KnowledgeIngestionService(
                SqlAlchemyKnowledgeRepository(session),
                storage,
                provider,
                storage_bucket=settings.rag_storage_bucket,
                poll_interval_seconds=2,
            )
            for entry in entries:
                result = await service.ingest(
                    entry,
                    args.source_root,
                    args.approved_by,
                    retry_failed=args.retry_failed,
                    normalize_provider_pdf=args.normalize_provider_pdf,
                    provider_text_derivative=args.provider_text_derivative,
                )
                print(f"{result.source_key}: {result.status} cached={result.cached}")
    finally:
        await engine.dispose()


def main() -> None:
    args = _parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
