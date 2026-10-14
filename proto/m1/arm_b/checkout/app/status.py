"""Order status, derived from the core's facts. The core does not know about statuses."""

from checkout.core.api import Order


def status(order: Order) -> str:
    if order.hold == "released":
        return "expired"
    if order.open_refunds:
        return "refunding"
    if order.charge is not None:
        return "refunded" if order.refunded and order.refunded == order.charge.amount else "paid"
    if order.open_charge is not None:
        return "paying"
    return "reserved"
