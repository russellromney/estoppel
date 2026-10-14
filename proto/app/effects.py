"""External world: a simulated clock and a payment provider.

The provider behaves like a real payment API with idempotency keys:
executing the same op_id twice applies it at most once. It is the
ground truth for money, so safety invariants about charges and refunds
are checked against its ledger, not against the kernel's own records.

Faults model what a caller can observe over a network:
  ok           applied, response delivered
  declined     rejected by the provider, nothing applied
  lost_after   applied, but the response was lost (caller sees a timeout)
  lost_before  never reached the provider (caller sees a timeout)
"""

from dataclasses import dataclass


class Clock:
    def __init__(self, now: int = 0):
        self.now = now

    def advance(self, seconds: int):
        self.now += seconds


@dataclass(frozen=True)
class Applied:
    op_id: str
    kind: str  # "charge" | "refund"
    order_id: str
    amount: int
    recipient: str


class PaymentProvider:
    def __init__(self):
        self.applied: dict[str, Applied] = {}
        self.declined: set[str] = set()
        self.calls = 0

    def execute(self, op_id, kind, order_id, amount, recipient, fault="ok") -> str:
        """Return "ok", "declined" or "timeout" as seen by the caller."""
        self.calls += 1
        if fault == "lost_before":
            return "timeout"
        if op_id in self.applied:
            result = "ok"
        elif op_id in self.declined:
            result = "declined"
        elif fault == "declined":
            self.declined.add(op_id)
            result = "declined"
        else:
            self.applied[op_id] = Applied(op_id, kind, order_id, amount, recipient)
            result = "ok"
        if fault == "lost_after":
            return "timeout"
        return result

    def lookup(self, op_id) -> str:
        """Reconciliation query: "applied", "declined" or "absent"."""
        if op_id in self.applied:
            return "applied"
        if op_id in self.declined:
            return "declined"
        return "absent"

    # Ground-truth views used by invariants.
    def total(self, kind: str, order_id: str) -> int:
        return sum(a.amount for a in self.applied.values()
                   if a.kind == kind and a.order_id == order_id)

    def count(self, kind: str, order_id: str) -> int:
        return sum(1 for a in self.applied.values()
                   if a.kind == kind and a.order_id == order_id)
