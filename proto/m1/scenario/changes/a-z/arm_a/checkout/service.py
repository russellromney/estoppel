"""Checkout service: request handlers, background jobs and read views."""

from collections.abc import Callable, Mapping

from checkout.config import COUPONS, PRICES
from checkout.gateway import PaymentGateway
from checkout.models import Order, OrderStatus, Outcome, Payment
from checkout.policies import hold_lapsed, refund_window_open
from checkout.pricing import apply_coupon, order_total
from checkout.store import Store
from checkout.validation import parse_items, valid_coupon
from spec import OrderView, Response
from world import Clock


def accepted(order: Order) -> Response:
    return Response(ok=True, order_id=order.id, price=order.price, status=order.status.value)


def rejected(reason: str) -> Response:
    return Response(ok=False, reason=reason)


def view(order: Order) -> OrderView:
    return OrderView(id=order.id, customer=order.customer, items=order.items,
                     price=order.price, status=order.status.value,
                     reserved_at=order.reserved_at, charged_at=order.charged_at,
                     refunded=order.refunded, coupon=order.coupon)


class CheckoutService:
    def __init__(self, store: Store, gateway: PaymentGateway, clock: Clock,
                 prices: Mapping[str, int] = PRICES):
        self.store = store
        self.gateway = gateway
        self.clock = clock
        self.prices = prices

    # ------------------------------------------------------------------
    # Requests

    def place_order(self, request_id: str, customer: str, items, coupon=None) -> Response:
        return self._once(request_id, lambda: self._place_order(customer, items, coupon))

    def pay(self, request_id: str, customer: str, order_id: str) -> Response:
        return self._once(request_id, lambda: self._pay(customer, order_id))

    def refund(self, request_id: str, customer: str, order_id: str) -> Response:
        return self._once(request_id, lambda: self._refund(customer, order_id))

    def _once(self, request_id: str, handle: Callable[[], Response]) -> Response:
        """Process a request at most once; repeats get the stored response."""
        record = self.store.get_request(request_id)
        if record is not None:
            return record.response or rejected("in_progress")
        self.store.begin_request(request_id)
        try:
            response = handle()
        except BaseException:
            self.store.abandon_request(request_id)
            raise
        self.store.finish_request(request_id, response)
        return response

    def _place_order(self, customer: str, items, coupon) -> Response:
        lines = parse_items(items, self.prices)
        if lines is None:
            return rejected("bad_items")
        if coupon is not None and not valid_coupon(coupon, COUPONS):
            return rejected("bad_coupon")
        if not self.store.has_stock(lines):
            return rejected("out_of_stock")
        if coupon is not None and self.store.redemptions(coupon) >= COUPONS[coupon]:
            return rejected("coupon_used_up")
        order = Order(
            id=self.store.next_order_id(),
            customer=customer,
            items=tuple(sorted(lines.items())),
            price=apply_coupon(order_total(lines, self.prices), coupon),
            status=OrderStatus.RESERVED,
            reserved_at=self.clock.now,
            coupon=coupon,
        )
        self.store.take_stock(lines)
        self.store.add_order(order)
        return accepted(order)

    def _pay(self, customer: str, order_id: str) -> Response:
        order = self.store.find_order(order_id, customer)
        if order is None:
            return rejected("not_found")
        if order.status == OrderStatus.EXPIRED or (
                order.status == OrderStatus.RESERVED and hold_lapsed(order, self.clock.now)):
            return rejected("expired")
        if order.status != OrderStatus.RESERVED:
            return rejected("not_payable")
        # A new attempt starts only after the previous one was declined,
        # so attempt numbers give each charge call its own idempotency key.
        attempt = len(self.store.payments_for(order.id, "charge")) + 1
        payment = Payment(key=f"charge-{order.id}-{attempt}", kind="charge", order_id=order.id,
                          customer=order.customer, amount=order.price,
                          created_at=self.clock.now)
        self.store.add_payment(payment)
        order.status = OrderStatus.PAYING
        self._send(payment)
        if payment.state == "declined":
            return rejected("declined")
        return accepted(self.store.get_order(order.id))

    def _refund(self, customer: str, order_id: str) -> Response:
        order = self.store.find_order(order_id, customer)
        if order is None:
            return rejected("not_found")
        if order.status != OrderStatus.PAID:
            return rejected("not_refundable")
        if not refund_window_open(order, self.clock.now):
            return rejected("window_closed")
        number = len(self.store.payments_for(order.id, "refund")) + 1
        payment = Payment(key=f"refund-{order.id}-{number}", kind="refund", order_id=order.id,
                          customer=order.customer, amount=order.price - order.refunded,
                          created_at=self.clock.now)
        self.store.add_payment(payment)
        order.status = OrderStatus.REFUNDING
        self._send(payment)
        if payment.state == "declined":
            return rejected("declined")
        return accepted(self.store.get_order(order.id))

    # ------------------------------------------------------------------
    # Provider calls

    def _send(self, payment: Payment):
        self._record(payment, self.gateway.send(payment))

    def _record(self, payment: Payment, outcome: Outcome):
        """Apply a provider outcome to the payment and its order."""
        if outcome.status == "unknown":
            payment.state = "unknown"
            return
        payment.state = outcome.status
        order = self.store.get_order(payment.order_id)
        applied = outcome.status == "applied"
        if payment.kind == "charge":
            if applied:
                order.status = OrderStatus.PAID
                order.charged_at = outcome.at
            else:
                order.status = OrderStatus.RESERVED
        elif applied:
            order.refunded += payment.amount
            order.status = OrderStatus.REFUNDED
        else:
            order.status = OrderStatus.PAID

    # ------------------------------------------------------------------
    # Background jobs

    def run_jobs(self):
        self.expire_lapsed_holds()
        self.reconcile_payments()

    def expire_lapsed_holds(self):
        now = self.clock.now
        for order in list(self.store.orders.values()):
            if order.status == OrderStatus.RESERVED and hold_lapsed(order, now):
                order.status = OrderStatus.EXPIRED
                self.store.release_stock(order)

    def reconcile_payments(self):
        """Settle provider calls whose outcome is unknown."""
        for payment in self.store.payments_in_state("unknown"):
            if payment.state != "unknown":  # settled by a job run during an earlier retry
                continue
            outcome = self.gateway.lookup(payment.key)
            if outcome is None:  # never reached the provider: retry with the same key
                payment.state = "in_flight"
                outcome = self.gateway.send(payment)
            self._record(payment, outcome)

    # ------------------------------------------------------------------
    # Views

    def order(self, order_id: str) -> OrderView | None:
        order = self.store.orders.get(order_id)
        return view(order) if order else None

    def orders(self) -> list[OrderView]:
        return [view(o) for o in self.store.orders.values()]

    def stock(self) -> dict[str, int]:
        return dict(self.store.stock)
