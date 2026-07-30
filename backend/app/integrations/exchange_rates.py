from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ExchangeRateQuote:
    rate: Decimal
    as_of: datetime


class ExchangeRateProviderError(Exception):
    pass


class ExchangeRateProvider(Protocol):
    async def get_rate(self, base_currency: str, display_currency: str) -> ExchangeRateQuote: ...


class FakeExchangeRateProvider:
    def __init__(
        self,
        rates: dict[tuple[str, str], Decimal] | None = None,
        *,
        as_of: datetime | None = None,
    ) -> None:
        self._rates = rates or {}
        self._as_of = as_of or datetime.now(UTC)
        self.calls: list[tuple[str, str]] = []

    async def get_rate(self, base_currency: str, display_currency: str) -> ExchangeRateQuote:
        self.calls.append((base_currency, display_currency))
        rate = self._rates.get((base_currency, display_currency))
        if rate is None:
            raise ExchangeRateProviderError
        return ExchangeRateQuote(rate=rate, as_of=self._as_of)
