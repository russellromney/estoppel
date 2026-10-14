"""The public interface (spec.Checkout). Each request runs a workflow through the core runtime."""

from checkout.app import workflows as wf
from checkout.app.views import rejected, view
from checkout.core.api import IN_PROGRESS, Runtime
from spec import OrderView, Response


class CheckoutService:
    def __init__(self, runtime: Runtime):
        self.runtime = runtime

    def place_order(self, request_id: str, customer: str, items) -> Response:
        return self._request(request_id, "place_order", customer, None,
                             lambda snap: wf.propose_place_order(customer, items, snap),
                             wf.respond_place_order)

    def pay(self, request_id: str, customer: str, order_id: str) -> Response:
        return self._request(request_id, "pay", customer, order_id,
                             lambda snap: wf.propose_pay(order_id, snap), wf.respond_payment)

    def refund(self, request_id: str, customer: str, order_id: str) -> Response:
        return self._request(request_id, "refund", customer, order_id,
                             lambda snap: wf.propose_refund(order_id, snap), wf.respond_payment)

    def _request(self, request_id, kind, customer, subject, propose, respond) -> Response:
        result = self.runtime.request(request_id, kind, customer, subject, propose, respond)
        return rejected("in_progress") if result is IN_PROGRESS else result

    def run_jobs(self):
        self.runtime.job("expire", wf.propose_expiry)
        self.runtime.reconcile()

    def order(self, order_id: str) -> OrderView | None:
        order = self.runtime.view().orders.get(order_id)
        return view(order) if order else None

    def orders(self) -> list[OrderView]:
        return [view(order) for order in self.runtime.view().orders.values()]

    def stock(self) -> dict[str, int]:
        return dict(self.runtime.view().stock)
