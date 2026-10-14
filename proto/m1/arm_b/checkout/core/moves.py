"""Plans: what the periphery proposes. The core decides whether a plan is allowed."""

from typing import Annotated, Literal

from pydantic import Field, StrictInt

from checkout.core.facts import Fact, Quote


class OpenOrder(Fact):
    """Accept a quote for a new order and hold stock for each of its lines until `hold_until`."""

    kind: Literal["open_order"] = "open_order"
    quote: Quote
    hold_until: StrictInt


class StartCharge(Fact):
    """Charge the order's customer the accepted quote's total."""

    kind: Literal["start_charge"] = "start_charge"
    order_id: str


class StartRefund(Fact):
    """Refund the order's payer these amounts, one per quote line."""

    kind: Literal["start_refund"] = "start_refund"
    order_id: str
    per_line: tuple[StrictInt, ...]


class Release(Fact):
    """Return the order's held stock."""

    kind: Literal["release"] = "release"
    order_id: str


Move = Annotated[OpenOrder | StartCharge | StartRefund | Release, Field(discriminator="kind")]


class Plan(Fact):
    moves: tuple[Move, ...] = Field(min_length=1)
