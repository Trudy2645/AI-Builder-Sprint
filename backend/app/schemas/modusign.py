import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DocumentStatus = Literal["ON_PROCESSING", "ON_GOING", "COMPLETED"]

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SignatureParticipant(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    role: Literal["바이어"]
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def email_must_look_valid(cls, value: str) -> str:
        if not _EMAIL_PATTERN.match(value):
            raise ValueError("email must be a valid email address")
        return value


class SignatureRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    buyer: SignatureParticipant


class BuyerFieldCreate(BaseModel):
    """A buyer-controlled field overlaid on the immutable source PDF."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    field_type: Literal["TEXT", "SIGNATURE", "CHECKBOX"]
    data_label: str = Field(min_length=1, max_length=100)
    position: dict[str, Any]
    size: dict[str, float] | None = None
    required: bool = True

    @model_validator(mode="after")
    def validate_position_and_size(self) -> "BuyerFieldCreate":
        coordinate_keys = {"x", "y", "page"}
        has_coordinates = coordinate_keys.issubset(self.position)
        has_anchor = "anchor" in self.position
        if has_coordinates == has_anchor:
            raise ValueError("position must contain coordinates or anchor, but not both")

        if has_anchor:
            anchor = self.position.get("anchor")
            if not isinstance(anchor, dict) or not isinstance(anchor.get("text"), str):
                raise ValueError("position.anchor.text is required")
            if not 1 <= len(anchor["text"]) <= 200:
                raise ValueError("position.anchor.text must be 1 to 200 characters")
            offset = anchor.get("offset")
            if offset is not None:
                if not isinstance(offset, dict) or not {"x", "y"}.issubset(offset):
                    raise ValueError("position.anchor.offset requires x and y")
                if not all(_number_between(offset[key], -1, 1) for key in ("x", "y")):
                    raise ValueError("anchor offsets must be between -1 and 1")
        else:
            if not isinstance(self.position.get("page"), int) or self.position["page"] < 1:
                raise ValueError("position.page must be a positive integer")
            if not all(_number_between(self.position[key], 0, 1) for key in ("x", "y")):
                raise ValueError("position coordinates must be between 0 and 1")

        if self.field_type == "SIGNATURE":
            if self.size is None or not {"width", "height"}.issubset(self.size):
                raise ValueError("signature fields require width and height")
            if not all(_number_between(self.size[key], 0.01, 1) for key in ("width", "height")):
                raise ValueError("signature size must be between 0.01 and 1")
            if has_coordinates and (
                float(self.position["x"]) + self.size["width"] > 1
                or float(self.position["y"]) + self.size["height"] > 1
            ):
                raise ValueError("signature field must fit inside the page")
        return self


def _number_between(value: Any, minimum: float, maximum: float) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and minimum <= float(value) <= maximum
    )


class SignatureRequestFromDocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    document_id: str
    title: str = Field(min_length=1, max_length=200)
    buyer: SignatureParticipant
    fields: list[BuyerFieldCreate] = Field(min_length=1, max_length=20)


class SignatureRequestResponse(BaseModel):
    document_id: str
    title: str
    status: DocumentStatus


class DocumentFile(BaseModel):
    download_url: str | None = None


class DocumentStatusResponse(BaseModel):
    document_id: str
    status: DocumentStatus
    current_signing_order: int | None = None
    file: DocumentFile | None = None
    audit_trail: DocumentFile | None = None
