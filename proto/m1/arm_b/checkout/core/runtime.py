"""The runtime: requests, jobs, provider calls and reconciliation.

A request runs one periphery workflow:
  propose(snapshot) -> Plan, or a final response
  commit the plan (the core decides)
  call the provider for every payment the plan started
  respond(snapshot, receipt) -> response
Nothing is held across a provider call; other requests and jobs may run during it.
"""

from collections.abc import Callable, Mapping

from checkout.core.authority import grant
from checkout.core.commit import State, commit, settle
from checkout.core.facts import Grant, Receipt, Snapshot
from checkout.core.moves import Plan
from world import Clock, PaymentDeclined, PaymentTimeout, Provider


class InProgress:
    def __repr__(self):
        return "IN_PROGRESS"


IN_PROGRESS = InProgress()
_PENDING = object()

Propose = Callable[[Snapshot], object]
Respond = Callable[[Snapshot, Receipt], object]


class Runtime:
    def __init__(self, clock: Clock, provider: Provider, stock: Mapping[str, int]):
        self._clock = clock
        self._provider = provider
        self._state = State(stock=dict(stock))
        self._requests: dict[str, object] = {}

    # ------------------------------------------------------------------
    # Entry points for the periphery

    def request(self, request_id: str, kind: str, customer: str, subject: str | None,
                propose: Propose, respond: Respond):
        """Run a customer request at most once. Repeats get the stored response, or IN_PROGRESS."""
        if request_id in self._requests:
            stored = self._requests[request_id]
            return IN_PROGRESS if stored is _PENDING else stored
        self._requests[request_id] = _PENDING
        try:
            response = self._run(grant(kind, "customer", customer, subject, self._state.orders),
                                 propose, respond)
        except BaseException:
            del self._requests[request_id]
            raise
        self._requests[request_id] = response
        return response

    def job(self, kind: str, propose: Propose) -> Receipt | None:
        """Run a background workflow. It returns a plan, or None when there is nothing to do."""
        result = self._run(grant(kind, "job", "job", None, self._state.orders), propose, None)
        return result if isinstance(result, Receipt) else None

    def view(self) -> Snapshot:
        return self._snapshot(grant("view", "operator", "operator", None, self._state.orders))

    def reconcile(self):
        """Settle provider calls whose outcome is unknown, looking each up by its key."""
        for key in list(self._state.payment_orders):
            if self._payment(key).state != "unknown":  # includes calls settled during an earlier retry
                continue
            found = self._provider.lookup(key)
            if found is None:  # never reached the provider: retry with the same key
                settle(self._state, key, "in_flight")
                self._send(key)
            elif found == "declined":
                settle(self._state, key, "declined")
            else:
                settle(self._state, key, "applied", found.at)

    # ------------------------------------------------------------------

    def _run(self, granted: Grant, propose: Propose, respond: Respond | None):
        proposal = propose(self._snapshot(granted))
        if not isinstance(proposal, Plan):
            return proposal
        receipt = commit(proposal, granted, self._state, self._clock.now)
        for payment in receipt.payments:
            self._send(payment.key)
        receipt = receipt.model_copy(update={
            "payments": tuple(self._payment(p.key) for p in receipt.payments)})
        if respond is None:
            return receipt
        return respond(self._snapshot(granted, receipt.opened), receipt)

    def _snapshot(self, granted: Grant, also: tuple[str, ...] = ()) -> Snapshot:
        orders = self._state.orders
        if granted.scope == "all":
            visible = dict(orders)
        else:
            ids = ((granted.subject,) if granted.subject else ()) + also
            visible = {i: orders[i] for i in ids}
        return Snapshot.model_construct(now=self._clock.now, grant=granted,
                                        stock=dict(self._state.stock), orders=visible)

    def _payment(self, key: str):
        order = self._state.orders[self._state.payment_orders[key]]
        return next(p for p in order.payments if p.key == key)

    def _send(self, key: str):
        payment = self._payment(key)
        customer = self._state.orders[payment.order_id].customer
        call = self._provider.charge if payment.kind == "charge" else self._provider.refund
        try:
            applied = call(key, customer, payment.order_id, payment.amount)
        except PaymentDeclined:
            settle(self._state, key, "declined")
        except PaymentTimeout:
            settle(self._state, key, "unknown")
        else:
            settle(self._state, key, "applied", applied.at)
