"""OCR-guided signer fields for an uploaded, non-template PDF."""

from typing import Any  # noqa: I001

from app.ai.schemas import DocumentParseResult


_FIELD_DEFINITIONS = (
    ("buyer_name", "TEXT", ("성명/단체명", "성명·단체명", "예약자 성명"), True, True),
    (
        "buyer_passport_or_nationality",
        "TEXT",
        ("국적·여권번호(외국인)", "국적·여권번호", "여권번호"),
        False,
        True,
    ),
    ("buyer_phone", "TEXT", ("연락처",), False, True),
    ("buyer_email", "TEXT", ("이메일",), False, True),
    ("contract_date", "TEXT", ("계약 체결일", "계약일"), False, False),
    ("service_period", "TEXT", ("이용 기간", "이용날짜"), False, False),
    ("requested_people", "TEXT", ("이용 인원", "이용인원"), False, False),
    ("buyer_signature", "SIGNATURE", ("바이어 서명", "예약자 서명", "을 서명"), True, True),
)


def signature_field_candidates(parsed: DocumentParseResult) -> list[dict[str, Any]]:
    """Find distinct input coordinates from OCR, including within one table block.

    Some uploaded PDFs are image-only. Modusign's PDF-text anchors cannot be
    used for them, so this always relies on the normalized coordinates returned
    by Document Parse. The text's line and character offset separates fields
    that otherwise share a table block's one bounding box.
    """
    blocks = [block for page in parsed.pages for block in page.blocks if block.content.strip()]
    candidates: list[dict[str, Any]] = []
    for data_label, field_type, markers, required, buyer_only in _FIELD_DEFINITIONS:
        candidate = _coordinate_candidate(
            blocks, data_label, field_type, markers, required, buyer_only
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _coordinate_candidate(
    blocks: list[Any],
    data_label: str,
    field_type: str,
    markers: tuple[str, ...],
    required: bool,
    buyer_only: bool,
) -> dict[str, Any] | None:
    for block in blocks:
        if block.bbox is None:
            continue
        bbox = block.bbox
        if not all(0 <= value <= 1 for value in (bbox.x, bbox.y, bbox.width, bbox.height)):
            continue
        start_at = 0
        if buyer_only:
            buyer_starts = [
                index
                for index in (block.content.find("바이어"), block.content.find("예약자"))
                if index >= 0
            ]
            if buyer_starts:
                start_at = min(buyer_starts)
            elif data_label in {
                "buyer_name",
                "buyer_passport_or_nationality",
                "buyer_phone",
                "buyer_email",
            }:
                continue
        marker = next(
            (value for value in markers if block.content.find(value, start_at) >= 0), None
        )
        if marker is None:
            continue
        index = block.content.find(marker, start_at)
        lines = block.content.splitlines() or [block.content]
        line_index = block.content[:index].count("\n")
        line = lines[min(line_index, len(lines) - 1)]
        marker_index = line.find(marker)
        x = bbox.x + bbox.width * (marker_index + len(marker) + 1) / max(len(line), 1)
        y = bbox.y + bbox.height * line_index / max(len(lines), 1)
        x = min(0.94, max(0.02, x))
        y = min(0.94, max(0.02, y))
        return {
            "data_label": data_label,
            "field_type": field_type,
            "position": {"page": block.page_number, "x": x, "y": y},
            "size": {
                "width": min(0.30 if field_type == "TEXT" else 0.25, 0.98 - x),
                "height": 0.06 if field_type == "SIGNATURE" else 0.04,
            },
            "required": required,
        }
    return None
