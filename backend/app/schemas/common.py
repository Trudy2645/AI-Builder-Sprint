from typing import Any

from fastapi import Request
from pydantic import BaseModel


class ResponseMeta(BaseModel):
    request_id: str


class SuccessEnvelope[DataT](BaseModel):
    data: DataT
    meta: ResponseMeta


def envelope(request: Request, data: Any) -> dict[str, Any]:
    return {
        "data": data,
        "meta": {"request_id": request.state.request_id},
    }


def typed_envelope[DataT](request: Request, data: DataT) -> SuccessEnvelope[DataT]:
    return SuccessEnvelope(data=data, meta=ResponseMeta(request_id=request.state.request_id))
