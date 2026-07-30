from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PriceEstimateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    people: int = Field(gt=0)
    quantity: int = Field(gt=0)
    quantity_unit: str = Field(min_length=1, max_length=32)
    nights: int = Field(gt=0)
    start_date: date
    end_date: date
    currency: str = Field(pattern=r"^[A-Z]{3}$")

    @model_validator(mode="after")
    def validate_stay(self) -> "PriceEstimateRequest":
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be later than start_date")
        if (self.end_date - self.start_date).days != self.nights:
            raise ValueError("nights must equal the number of days between start_date and end_date")
        return self


class PriceEstimate(BaseModel):
    base_unit_price_amount_minor: int = Field(ge=0)
    billing_quantity: int = Field(gt=0)
    quantity_unit: str
    nights: int = Field(gt=0)
    start_date: date
    end_date: date
    formula: str
    total_estimated_amount_minor: int = Field(ge=0)
    base_currency: str
    display_currency: str
    exchange_rate: Decimal = Field(gt=0)
    exchange_rate_as_of: datetime
    disclaimer: str
