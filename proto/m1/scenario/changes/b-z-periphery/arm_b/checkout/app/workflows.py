"""Workflows: pure functions that turn a request and a snapshot into a proposed plan.

Each `propose_*` returns a Plan for the core to decide on, or a final Response.
Each `respond_*` builds the response once the plan has been committed and its
provider calls made.
"""

from checkout.app.config import PRICES
from checkout.app.coupons import coupon_budget, known_coupon
from checkout.app.items import parse_items
from checkout.app.policies import hold_lapsed, hold_until, refund_window_open
from checkout.app.pricing.pipeline import quote
from checkout.app.pricing.types import Context
from checkout.app.status import status
from checkout.app.views import accepted, rejected
from checkout.core.api import OpenOrder, Plan, Receipt, Release, Snapshot, StartCharge, StartRefund
from spec import Response


def propose_place_order(customer: str, items, snap: Snapshot, coupon=None) -> Plan | Response:
    cart = parse_items(items, PRICES)
    if cart is None:
        return rejected("bad_items")
    if coupon is not None and not known_coupon(coupon):
        return rejected("bad_coupon")
    if any(snap.stock.get(sku, 0) < qty for sku, qty in cart):
        return rejected("out_of_stock")
    budgets = (coupon_budget(coupon),) if coupon is not None else ()
    if any(snap.budgets.get(name, 0) < 1 for name in budgets):
        return rejected("coupon_used_up")
    priced = quote(cart, Context(customer=customer, coupon=coupon))
    return Plan(moves=(OpenOrder(quote=priced, hold_until=hold_until(snap.now), budgets=budgets),))


def respond_place_order(snap: Snapshot, receipt: Receipt) -> Response:
    return accepted(snap.orders[receipt.opened[0]])


def propose_pay(order_id: str, snap: Snapshot) -> Plan | Response:
    order = snap.orders.get(order_id)
    if order is None:
        return rejected("not_found")
    current = status(order)
    if current == "expired" or (current == "reserved" and hold_lapsed(order, snap.now)):
        return rejected("expired")
    if current != "reserved":
        return rejected("not_payable")
    return Plan(moves=(StartCharge(order_id=order.id),))


def propose_refund(order_id: str, snap: Snapshot) -> Plan | Response:
    order = snap.orders.get(order_id)
    if order is None:
        return rejected("not_found")
    if status(order) != "paid":
        return rejected("not_refundable")
    if not refund_window_open(order, snap.now):
        return rejected("window_closed")
    return Plan(moves=(StartRefund(order_id=order.id, per_line=order.refundable_per_line),))


def respond_payment(snap: Snapshot, receipt: Receipt) -> Response:
    """For pay and refund: report the outcome if the provider gave one."""
    payment = receipt.payments[0]
    if payment.state == "declined":
        return rejected("declined")
    return accepted(snap.orders[payment.order_id])


def propose_expiry(snap: Snapshot) -> Plan | None:
    lapsed = [order.id for order in snap.orders.values()
              if status(order) == "reserved" and hold_lapsed(order, snap.now)]
    return Plan(moves=tuple(Release(order_id=i) for i in lapsed)) if lapsed else None
