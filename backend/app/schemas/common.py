from typing import Any

from fastapi import Request


def envelope(request: Request, data: Any) -> dict[str, Any]:
    return {
        "data": data,
        "meta": {"request_id": request.state.request_id},
    }
