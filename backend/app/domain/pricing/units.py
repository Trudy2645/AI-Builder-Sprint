from typing import Final, NamedTuple


class PriceUnitRule(NamedTuple):
    quantity_unit: str
    uses_nights: bool


PRICE_UNIT_RULES: Final[dict[str, PriceUnitRule]] = {
    "person": PriceUnitRule("person", False),
    "room": PriceUnitRule("room", False),
    "room_night": PriceUnitRule("room", True),
    "seat": PriceUnitRule("seat", False),
    "vehicle": PriceUnitRule("vehicle", False),
}
SUPPORTED_QUANTITY_UNITS: Final[frozenset[str]] = frozenset(
    rule.quantity_unit for rule in PRICE_UNIT_RULES.values()
)

_PRICE_UNIT_ALIASES: Final[dict[str, str]] = {
    "객실당": "room",
    "객실/박": "room_night",
    "객실 1박": "room_night",
    "room/night": "room_night",
    "room per night": "room_night",
    "1인당": "person",
    "인당": "person",
    "좌석당": "seat",
    "차량당": "vehicle",
    "대당": "vehicle",
    "1동당": "vehicle",
}


def canonical_price_unit(value: str | None) -> str | None:
    """Map OCR/UI display labels to the provider's canonical price units."""
    if value is None:
        return None
    normalized = " ".join(value.strip().lower().split())
    return _PRICE_UNIT_ALIASES.get(normalized, normalized)
