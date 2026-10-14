"""In-memory persistence: orders, stock, provider calls and idempotency records.

Stands in for a database. Every method is a single atomic operation;
handlers hold no lock across a provider call.
"""

import itertools
from collections.abc import Mapping

from checkout.models import HOLDS_STOCK, Order, OrderStatus, Payment, RequestRecord


class Store:
    def __init__(self, prices: Mapping[str, int], initial_stock: int):
        self.stock = {sku: initial_stock for sku in prices}
        self.orders: dict[str, Order] = {}
        self.payments: dict[str, Payment] = {}
        self.requests: dict[str, RequestRecord] = {}
        self._ids = itertools.count(1)

    # Orders and stock

    def next_order_id(self) -> str:
        return f"ord-{next(self._ids)}"

    def add_order(self, order: Order):
        self.orders[order.id] = order

    def get_order(self, order_id: str) -> Order:
        return self.orders[order_id]

    def find_order(self, order_id: str, customer: str) -> Order | None:
        """Tenant-scoped lookup: another customer's order is not found."""
        order = self.orders.get(order_id)
        if order is None or order.customer != customer:
            return None
        return order

    def has_stock(self, lines: Mapping[str, int]) -> bool:
        return all(self.stock[sku] >= qty for sku, qty in lines.items())

    def take_stock(self, lines: Mapping[str, int]):
        for sku, qty in lines.items():
            self.stock[sku] -= qty

    def release_stock(self, order: Order):
        for sku, qty in order.items:
            self.stock[sku] += qty

    def redemptions(self, coupon: str) -> int:
        """Orders that hold a redemption of the coupon: every order that used it and has not expired."""
        return sum(1 for o in self.orders.values()
                   if o.coupon == coupon and o.status != OrderStatus.EXPIRED)

    def held_units(self, sku: str) -> int:
        return sum(q for o in self.orders.values() if o.status in HOLDS_STOCK
                   for s, q in o.items if s == sku)

    # Provider calls

    def add_payment(self, payment: Payment):
        self.payments[payment.key] = payment

    def payments_for(self, order_id: str, kind: str) -> list[Payment]:
        return [p for p in self.payments.values() if p.order_id == order_id and p.kind == kind]

    def payments_in_state(self, state: str) -> list[Payment]:
        return [p for p in self.payments.values() if p.state == state]

    # Idempotency

    def get_request(self, request_id: str) -> RequestRecord | None:
        return self.requests.get(request_id)

    def begin_request(self, request_id: str):
        self.requests[request_id] = RequestRecord(request_id=request_id)

    def finish_request(self, request_id: str, response):
        self.requests[request_id].response = response

    def abandon_request(self, request_id: str):
        self.requests.pop(request_id, None)
