"""The service interface every M1 arm implements, and the constants in REQUIREMENTS.md.

Each arm has a package `checkout` with `build(clock, provider) -> Checkout`.
The interface types here are the API contract, like a published schema.
Arms keep their own copies of catalog and policy constants; the
constants below are for the acceptance suite.
"""

from typing import Protocol

from pydantic import BaseModel, ConfigDict

PRICES = {"A": 1000, "B": 2500, "C": 400, "D": 9900}
INITIAL_STOCK = 6
HOLD = 900
REFUND_WINDOW = 2_592_000

STATUSES = ("reserved", "paying", "paid", "refunding", "refunded", "expired")
HOLDING = ("reserved", "paying", "paid", "refunding", "refunded")
REASONS = ("bad_items", "out_of_stock", "not_found", "expired", "not_payable",
           "not_refundable", "window_closed", "declined", "in_progress", "bad_amount")

Items = tuple[tuple[str, int], ...]


class Response(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool
    reason: str | None = None
    order_id: str | None = None
    price: int | None = None
    status: str | None = None


class OrderView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    customer: str
    items: Items
    price: int
    status: str
    reserved_at: int
    charged_at: int | None
    refunded: int


class Checkout(Protocol):
    def place_order(self, request_id: str, customer: str, items) -> Response: ...

    def pay(self, request_id: str, customer: str, order_id: str) -> Response: ...

    # partial_refunds adds a keyword argument: amount: int | None = None
    def refund(self, request_id: str, customer: str, order_id: str) -> Response: ...

    def run_jobs(self) -> None: ...

    def order(self, order_id: str) -> OrderView | None: ...

    def orders(self) -> list[OrderView]: ...

    def stock(self) -> dict[str, int]: ...
