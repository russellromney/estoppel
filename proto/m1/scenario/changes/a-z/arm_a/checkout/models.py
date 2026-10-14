from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from spec import Response


class OrderStatus(StrEnum):
    RESERVED = "reserved"
    PAYING = "paying"
    PAID = "paid"
    REFUNDING = "refunding"
    REFUNDED = "refunded"
    EXPIRED = "expired"


HOLDS_STOCK = frozenset(OrderStatus) - {OrderStatus.EXPIRED}


class Order(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    id: str
    customer: str
    items: tuple[tuple[str, int], ...]
    price: int
    status: OrderStatus
    reserved_at: int
    charged_at: int | None = None
    refunded: int = 0
    coupon: str | None = None


class Payment(BaseModel):
    """One call to the payment provider, charge or refund, identified by its idempotency key."""

    model_config = ConfigDict(validate_assignment=True)

    key: str
    kind: Literal["charge", "refund"]
    order_id: str
    customer: str
    amount: int
    created_at: int
    state: Literal["in_flight", "unknown", "applied", "declined"] = "in_flight"


class Outcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["applied", "declined", "unknown"]
    at: int | None = None  # provider time, when applied


class RequestRecord(BaseModel):
    """Idempotency record. `response` is None while the request is being processed."""

    request_id: str
    response: Response | None = None
