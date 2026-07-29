from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.schemas.common import envelope

router = APIRouter(prefix="/health", tags=["health"])


async def check_database_connection(
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if settings.database_url is None:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DATABASE_NOT_CONFIGURED",
            message="Database connection is not configured.",
        )

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DATABASE_UNAVAILABLE",
            message="Database connection is unavailable.",
        ) from exc
    finally:
        await engine.dispose()


@router.get("/live")
async def live(request: Request) -> dict:
    return envelope(request, {"status": "ok"})


@router.get("/ready", dependencies=[Depends(check_database_connection)])
async def ready(request: Request) -> dict:
    return envelope(request, {"status": "ready", "database": "connected"})
