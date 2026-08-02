"""Safe Modusign signer-field placement for final contract PDFs."""

from __future__ import annotations

import re
from typing import Any

from app.ai.schemas import DocumentParseResult

_SIGNATURE_MARKERS = ("바이어 서명", "예약자 서명")
_SIGNATURE_WIDTH = 0.20
_SIGNATURE_HEIGHT = 0.06
_FIELD_MARGIN = 0.01


class SignatureFieldPositionError(ValueError):
    """The final PDF has no trustworthy buyer-signature placement."""


def anchor_signature_field(page_texts: list[str]) -> dict[str, Any] | None:
    """Return a Modusign text anchor only when it is unique in the final PDF."""
    for marker in _SIGNATURE_MARKERS:
        if sum(text.count(marker) for text in page_texts) == 1:
            return {
                "data_label": "buyer_signature",
                "field_type": "SIGNATURE",
                "position": {
                    "anchor": {
                        "text": marker,
                        "offset": {"x": _FIELD_MARGIN, "y": 0.005},
                    }
                },
                "size": {"width": 0.15, "height": 0.05},
                "required": True,
                "placement_strategy": "anchor",
            }
    return None


def signature_field_candidates(parsed: DocumentParseResult) -> list[dict[str, Any]]:
    """Find an image-PDF signature field from a dedicated OCR marker block.

    A table-level bounding box cannot locate a cell accurately. Only a short,
    single-line OCR element containing one explicit buyer marker is accepted.
    The field is placed to the right of that element using its real normalized
    bounding box. Documents without such an element require manual placement.
    """
    for page in parsed.pages:
        for block in page.blocks:
            candidate = _ocr_marker_candidate(block)
            if candidate is not None:
                return [candidate]
    return []


def select_signature_field(
    *,
    page_texts: list[str],
    candidates: list[dict[str, Any]] | None,
    page_count: int,
) -> dict[str, Any]:
    """Select and validate one field, preferring a final-PDF text anchor."""
    anchor = anchor_signature_field(page_texts)
    if anchor is not None:
        return anchor

    allowed = {"manual_coordinate": 0, "ocr_marker_bbox": 1}
    ordered = sorted(
        (candidate for candidate in candidates or [] if isinstance(candidate, dict)),
        key=lambda candidate: allowed.get(str(candidate.get("placement_strategy")), 99),
    )
    for candidate in ordered:
        strategy = str(candidate.get("placement_strategy"))
        if strategy not in allowed:
            continue
        if candidate.get("data_label") != "buyer_signature":
            continue
        if candidate.get("field_type") != "SIGNATURE":
            continue
        if _valid_coordinate_field(candidate, page_count):
            return candidate
    raise SignatureFieldPositionError(
        "A unique text anchor, manual coordinate, or dedicated OCR marker is required."
    )


def _ocr_marker_candidate(block: Any) -> dict[str, Any] | None:
    if block.bbox is None or str(block.block_type).lower() == "table":
        return None
    content = " ".join(str(block.content).split())
    if "\n" in str(block.content) or len(content) > 30:
        return None
    marker = next((value for value in _SIGNATURE_MARKERS if value in content), None)
    if marker is None:
        return None
    remaining = re.sub(re.escape(marker), "", content, count=1).strip(" ()[]:：_-인")
    if remaining:
        return None

    bbox = block.bbox
    if not _normalized_box(bbox.x, bbox.y, bbox.width, bbox.height):
        return None
    x = bbox.x + bbox.width + _FIELD_MARGIN
    y = max(_FIELD_MARGIN, bbox.y + (bbox.height - _SIGNATURE_HEIGHT) / 2)
    if x + _SIGNATURE_WIDTH > 1 - _FIELD_MARGIN:
        return None
    y = min(y, 1 - _FIELD_MARGIN - _SIGNATURE_HEIGHT)
    return {
        "data_label": "buyer_signature",
        "field_type": "SIGNATURE",
        "position": {"page": block.page_number, "x": x, "y": y},
        "size": {"width": _SIGNATURE_WIDTH, "height": _SIGNATURE_HEIGHT},
        "required": True,
        "placement_strategy": "ocr_marker_bbox",
    }


def _valid_coordinate_field(candidate: dict[str, Any], page_count: int) -> bool:
    position = candidate.get("position")
    size = candidate.get("size")
    if not isinstance(position, dict) or not isinstance(size, dict):
        return False
    try:
        page = int(position["page"])
        x = float(position["x"])
        y = float(position["y"])
        width = float(size["width"])
        height = float(size["height"])
    except (KeyError, TypeError, ValueError):
        return False
    return (
        1 <= page <= page_count
        and _normalized_box(x, y, width, height)
        and width >= 0.01
        and height >= 0.01
    )


def _normalized_box(x: float, y: float, width: float, height: float) -> bool:
    return (
        0 <= x < 1
        and 0 <= y < 1
        and 0 < width <= 1
        and 0 < height <= 1
        and x + width <= 1
        and y + height <= 1
    )
