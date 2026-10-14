"""Public views of orders and request outcomes."""

from checkout.app.status import status
from checkout.core.api import Order
from spec import OrderView, Response


def view(order: Order) -> OrderView:
    return OrderView(id=order.id, customer=order.customer,
                     items=tuple((line.sku, line.qty) for line in order.quote.lines),
                     price=order.quote.total, status=status(order), reserved_at=order.opened_at,
                     charged_at=order.charge.at if order.charge else None, refunded=order.refunded)


def accepted(order: Order) -> Response:
    return Response(ok=True, order_id=order.id, price=order.quote.total, status=status(order))


def rejected(reason: str) -> Response:
    return Response(ok=False, reason=reason)
