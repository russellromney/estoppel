"""Facts: immutable records of what has happened. The core replaces them; nothing mutates them.

The periphery receives facts in snapshots and may read them freely.
Order status is not a fact; the periphery derives it.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator


class Fact(BaseModel):
    model_config = ConfigDict(frozen=True)


class Line(Fact):
    sku: str
    qty: StrictInt = Field(ge=1)
    unit_price: StrictInt = Field(ge=0)

    @property
    def gross(self) -> int:
        return self.qty * self.unit_price


class Adjustment(Fact):
    """A price change made by one pricing rule, allocated to quote lines. Negative is a discount."""

    rule: str
    per_line: tuple[StrictInt, ...]

    @property
    def amount(self) -> int:
        return sum(self.per_line)


class Quote(Fact):
    """What the customer is asked to pay, line by line. A quote is valid by construction."""

    lines: tuple[Line, ...] = Field(min_length=1)
    adjustments: tuple[Adjustment, ...] = ()

    @model_validator(mode="after")
    def _consistent(self):
        skus = [line.sku for line in self.lines]
        if len(set(skus)) != len(skus):
            raise ValueError("a quote has one line per SKU")
        for adjustment in self.adjustments:
            if len(adjustment.per_line) != len(self.lines):
                raise ValueError(f"adjustment {adjustment.rule} is not allocated to every line")
        if any(total < 0 for total in self.line_totals()):
            raise ValueError("line totals must not be negative")
        return self

    def line_totals(self) -> tuple[int, ...]:
        return tuple(line.gross + sum(a.per_line[i] for a in self.adjustments)
                     for i, line in enumerate(self.lines))

    @property
    def total(self) -> int:
        return sum(self.line_totals())


PaymentState = Literal["in_flight", "unknown", "applied", "declined"]
OPEN = ("in_flight", "unknown")


class Payment(Fact):
    """One provider call, a charge or a refund, identified by its idempotency key."""

    key: str
    kind: Literal["charge", "refund"]
    order_id: str
    amount: int
    per_line: tuple[int, ...]
    created_at: int
    state: PaymentState = "in_flight"
    at: int | None = None  # provider time, once applied


class Order(Fact):
    """An accepted quote, the stock held for it, and the money moved for it."""

    id: str
    customer: str
    quote: Quote
    opened_at: int
    hold_until: int
    hold: Literal["held", "consumed", "released"] = "held"
    payments: tuple[Payment, ...] = ()

    def _payments(self, kind, states) -> list[Payment]:
        return [p for p in self.payments if p.kind == kind and p.state in states]

    @property
    def charge(self) -> Payment | None:
        """The applied charge, if any. There is at most one."""
        return next(iter(self._payments("charge", ("applied",))), None)

    @property
    def open_charge(self) -> Payment | None:
        return next(iter(self._payments("charge", OPEN)), None)

    @property
    def open_refunds(self) -> list[Payment]:
        return self._payments("refund", OPEN)

    def _sum_lines(self, payments) -> tuple[int, ...]:
        return tuple(sum(p.per_line[i] for p in payments) for i in range(len(self.quote.lines)))

    @property
    def paid_per_line(self) -> tuple[int, ...]:
        return self.quote.line_totals() if self.charge else (0,) * len(self.quote.lines)

    @property
    def refunded_per_line(self) -> tuple[int, ...]:
        return self._sum_lines(self._payments("refund", ("applied",)))

    @property
    def pending_refund_per_line(self) -> tuple[int, ...]:
        return self._sum_lines(self.open_refunds)

    @property
    def refundable_per_line(self) -> tuple[int, ...]:
        return tuple(paid - done - pending for paid, done, pending in
                     zip(self.paid_per_line, self.refunded_per_line, self.pending_refund_per_line))

    @property
    def refunded(self) -> int:
        return sum(self.refunded_per_line)


class Grant(Fact):
    """The moves a request may propose, and the orders it may touch."""

    kind: str
    principal: str
    moves: frozenset[str]
    scope: Literal["new", "subject", "all"]
    subject: str | None = None  # for scope "subject": the order, if the principal owns it


class Snapshot(Fact):
    """What a workflow may read: the time, its grant, stock, and the orders in its scope."""

    now: int
    grant: Grant
    stock: dict[str, int]
    orders: dict[str, Order]


class Receipt(Fact):
    """What a committed plan did. Payments show their state after the provider was called."""

    opened: tuple[str, ...] = ()
    payments: tuple[Payment, ...] = ()
