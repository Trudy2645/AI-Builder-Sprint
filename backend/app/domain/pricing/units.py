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
