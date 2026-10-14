"""Checkout kernel: the only component that changes state or performs effects.

The kernel does three things:
  1. Builds tenant-scoped snapshots and issues narrowly authorized moves
     (grants) for a single request. A grant fixes the order, the amount,
     the recipient, the operation id and an expiry.
  2. Validates a planner's plan against *current* state (not the
     planner's snapshot), consumes the grant, and applies the plan.
  3. Runs external effects through an explicit model:
     pending -> in_flight -> completed | failed | unknown, with
     reconciliation of unknown effects by stable op_id.

Invariants the kernel enforces for every accepted plan (planner changes
do not need to re-establish these):
  - stock never goes negative; reserved items exist; quantities positive
  - 0 <= order price <= list total
  - one charge per order, for the order price, to the order's customer
  - refunds only of paid orders, full amount (v0), to the payer
  - every move uses an unexpired grant issued for this request, once

Everything else (correct price, refund window, reserving what the
customer asked for) is a planner obligation.

Methods are small on purpose so that kernel bug variants in
corpus/kernel_bugs.py can override one behaviour each.
"""

from dataclasses import dataclass

TTL = 900          # reservation hold, seconds
GRANT_TTL = 300    # how long an authorized move stays valid
PRICES = {"A": 1000, "B": 2500, "C": 400, "D": 9900}
INITIAL_STOCK = 6

LIVE_STATUSES = ("reserved", "paying", "paid", "refunding", "refunded")


@dataclass
class Order:
    id: str
    customer: str
    items: tuple  # ((sku, qty), ...)
    price: int
    status: str
    reserved_at: int
    paid_at: int | None = None
    refunded: int = 0

    def view(self) -> dict:
        return {
            "id": self.id, "status": self.status, "items": self.items,
            "price": self.price, "reserved_at": self.reserved_at,
            "paid_at": self.paid_at, "refunded": self.refunded,
        }


@dataclass
class Grant:
    id: str
    kind: str  # "reserve" | "charge" | "refund"
    request_id: str
    customer: str
    order_id: str
    amount: int
    recipient: str
    op_id: str
    expires_at: int
    used: bool = False


@dataclass
class Effect:
    op_id: str
    kind: str  # "charge" | "refund"
    order_id: str
    amount: int
    recipient: str
    status: str = "pending"


class Kernel:
    version = "kernel@v0"

    def __init__(self, clock, provider, prices=PRICES, initial_stock=INITIAL_STOCK):
        self.clock = clock
        self.provider = provider
        self.prices = dict(prices)
        self.stock = {sku: initial_stock for sku in self.prices}
        self.initial_stock = dict(self.stock)
        self.orders: dict[str, Order] = {}
        self.grants: dict[str, Grant] = {}
        self.effects: dict[str, Effect] = {}
        self.anomalies: list[str] = []
        self._counter = 0

    def next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}{self._counter}"

    # ------------------------------------------------------------------
    # Snapshots and authorized moves

    def issue(self, req, kind, order_id, amount, recipient) -> Grant:
        grant = Grant(
            id=self.next_id("g"), kind=kind, request_id=req["id"],
            customer=req["customer"], order_id=order_id, amount=amount,
            recipient=recipient, op_id=self.next_id("op"),
            expires_at=self.clock.now + GRANT_TTL,
        )
        self.grants[grant.id] = grant
        return grant

    def snapshot(self, req) -> dict:
        snap = {"now": self.clock.now, "customer": req["customer"], "grants": {}}
        kind = req["kind"]
        if kind == "place_order":
            snap["catalog"] = {
                sku: {"price": price, "stock": self.stock[sku]}
                for sku, price in self.prices.items()
            }
            g = self.issue(req, "reserve", self.next_id("o"), 0, req["customer"])
            snap["grants"][g.id] = {"kind": "reserve", "order_id": g.order_id,
                                    "expires_at": g.expires_at}
            return snap

        order = self.orders.get(req["order_id"])
        if order is None or order.customer != req["customer"]:
            snap["order"] = None  # tenant scoping: other customers' orders are invisible
            return snap
        snap["order"] = order.view()
        if kind == "pay" and order.status == "reserved":
            g = self.issue(req, "charge", order.id, order.price, order.customer)
            snap["grants"][g.id] = {"kind": "charge", "order_id": order.id,
                                    "amount": g.amount, "expires_at": g.expires_at}
        if kind == "refund" and self.refundable(order):
            g = self.issue(req, "refund", order.id, order.price - order.refunded,
                           order.customer)
            snap["grants"][g.id] = {"kind": "refund", "order_id": order.id,
                                    "amount": g.amount, "expires_at": g.expires_at}
        return snap

    def refundable(self, order: Order) -> bool:
        return order.status == "paid" and order.refunded == 0

    # ------------------------------------------------------------------
    # Commit

    def commit(self, req, plan) -> tuple[bool, str]:
        """Validate a plan against current state and apply it.

        Returns (accepted, reason). Rejections caused by the planner
        declining are prefixed with "planner:".
        """
        if not isinstance(plan, dict) or "op" not in plan:
            return False, "malformed_plan"
        op = plan["op"]
        if op == "reject":
            return False, f"planner:{plan.get('reason', '')}"
        if op == "error":
            return False, "planner_error"
        expected_kind = {"reserve": "reserve", "charge": "charge", "refund": "refund"}.get(op)
        if expected_kind is None:
            return False, "unknown_op"
        grant = self.grants.get(plan.get("grant"))
        if grant is None or grant.request_id != req["id"]:
            return False, "unknown_grant"
        if grant.kind != expected_kind:
            return False, "grant_kind"
        if grant.used:
            return False, "grant_used"
        if self.clock.now > grant.expires_at:
            return False, "grant_expired"
        return getattr(self, f"commit_{op}")(grant, plan)

    def consume(self, grant: Grant):
        grant.used = True

    def commit_reserve(self, grant, plan):
        items = plan.get("items")
        if not isinstance(items, tuple) or not items:
            return False, "bad_items"
        wanted: dict[str, int] = {}
        for line in items:
            if not (isinstance(line, tuple) and len(line) == 2):
                return False, "bad_items"
            sku, qty = line
            if sku not in self.prices:
                return False, "bad_items"
            if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
                return False, "bad_qty"
            wanted[sku] = wanted.get(sku, 0) + qty
        if not self.check_stock(wanted):
            return False, "insufficient_stock"
        price = plan.get("price")
        list_total = sum(self.prices[sku] * qty for sku, qty in wanted.items())
        if not isinstance(price, int) or isinstance(price, bool) or not 0 <= price <= list_total:
            return False, "price_out_of_bounds"
        self.consume(grant)
        for sku, qty in wanted.items():
            self.stock[sku] -= qty
        self.orders[grant.order_id] = Order(
            id=grant.order_id, customer=grant.customer,
            items=tuple(sorted(wanted.items())), price=price,
            status="reserved", reserved_at=self.clock.now,
        )
        return True, "reserved"

    def check_stock(self, wanted: dict[str, int]) -> bool:
        return all(self.stock[sku] >= qty for sku, qty in wanted.items())

    def commit_charge(self, grant, plan):
        order = self.orders.get(grant.order_id)
        if order is None or order.status != "reserved":
            return False, "order_state"
        if grant.amount != order.price:
            return False, "amount_mismatch"
        self.consume(grant)
        order.status = "paying"
        self.effects[grant.op_id] = Effect(grant.op_id, "charge", order.id,
                                           order.price, grant.recipient)
        return True, "charging"

    def commit_refund(self, grant, plan):
        order = self.orders.get(grant.order_id)
        if order is None or not self.refundable(order):
            return False, "order_state"
        amount = plan.get("amount")
        if amount != grant.amount or amount != order.price - order.refunded:
            return False, "amount_mismatch"
        self.consume(grant)
        order.status = "refunding"
        self.effects[grant.op_id] = Effect(grant.op_id, "refund", order.id,
                                           amount, grant.recipient)
        return True, "refunding"

    # ------------------------------------------------------------------
    # External effects

    def pending_effects(self) -> list[str]:
        return [op for op, e in self.effects.items() if e.status == "pending"]

    def unknown_effects(self) -> list[str]:
        return [op for op, e in self.effects.items() if e.status == "unknown"]

    def begin_delivery(self, op_id: str) -> Effect:
        effect = self.effects[op_id]
        effect.status = "in_flight"
        return effect

    def on_result(self, op_id: str, result: str):
        effect = self.effects[op_id]
        if effect.status != "in_flight":
            return  # stale response
        if result == "ok":
            self.complete(effect)
        elif result == "declined":
            self.fail(effect)
        else:
            self.on_timeout(effect)

    def on_timeout(self, effect: Effect):
        effect.status = "unknown"

    def complete(self, effect: Effect):
        effect.status = "completed"
        order = self.orders[effect.order_id]
        if effect.kind == "charge":
            if order.status != "paying":
                self.anomalies.append(f"charge completed for {order.id} in {order.status}")
                return
            order.status = "paid"
            order.paid_at = self.clock.now
        else:
            order.refunded += effect.amount
            order.status = "refunded"

    def fail(self, effect: Effect):
        effect.status = "failed"
        order = self.orders[effect.order_id]
        if effect.kind == "charge":
            self.restore_after_failed_charge(order)
        else:
            order.status = "paid"

    def restore_after_failed_charge(self, order: Order):
        if order.status == "paying":
            order.status = "reserved"

    def reconcile(self):
        for op_id in self.unknown_effects():
            self.reconcile_one(self.effects[op_id])

    def reconcile_one(self, effect: Effect):
        found = self.provider.lookup(effect.op_id)
        if found == "applied":
            self.complete(effect)
        elif found == "declined":
            self.fail(effect)
        else:
            effect.status = "pending"  # never reached the provider: retry, same op_id

    # ------------------------------------------------------------------
    # Time

    def tick(self):
        for order in self.orders.values():
            if self.should_expire(order):
                order.status = "expired"
                for sku, qty in order.items:
                    self.stock[sku] += qty

    def should_expire(self, order: Order) -> bool:
        return order.status == "reserved" and self.clock.now - order.reserved_at >= TTL
