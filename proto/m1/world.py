"""The external world shared by every M1 arm: a clock and a fake payment provider.

Arms receive a Clock and a Provider when they are built. Neither belongs
to any arm. The provider's ledger is the ground truth for money.

Fault injection, per charge or refund call:
  ok           applied, response delivered
  declined     rejected, nothing applied
  lost_before  never reached the provider (caller sees a timeout)
  lost_after   applied, but the response was lost (caller sees a timeout)

`during(phase)` is called inside every charge and refund call, with
phase "before" (request in transit) and "after" (applied, response in
transit). Tests use it to run other work while a call is in flight.
Calls made from inside the hook do not trigger it again.
"""

from collections import deque
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict

FAULTS = ("ok", "declined", "lost_before", "lost_after")


class Clock:
    def __init__(self, now: int = 0):
        self.now = now

    def advance(self, seconds: int):
        if seconds < 0:
            raise ValueError("time only moves forward")
        self.now += seconds


class PaymentDeclined(Exception):
    pass


class PaymentTimeout(Exception):
    pass


class Applied(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    kind: Literal["charge", "refund"]
    customer: str
    order_id: str
    amount: int
    at: int


class Provider:
    def __init__(self, clock: Clock):
        self.clock = clock
        self.applied: dict[str, Applied] = {}
        self.declined: set[str] = set()
        self.faults: deque[str] = deque()
        self.choose_fault: Callable[[str, str], str] | None = None
        self.during: Callable[[str], None] | None = None
        self.calls = 0
        self._in_hook = False

    def charge(self, key: str, customer: str, order_id: str, amount: int) -> Applied:
        return self._execute("charge", key, customer, order_id, amount)

    def refund(self, key: str, customer: str, order_id: str, amount: int) -> Applied:
        return self._execute("refund", key, customer, order_id, amount)

    def lookup(self, key: str) -> Applied | Literal["declined"] | None:
        if key in self.applied:
            return self.applied[key]
        if key in self.declined:
            return "declined"
        return None

    # Ledger views used by checks.
    def charges(self, order_id: str) -> list[Applied]:
        return [a for a in self.applied.values() if a.kind == "charge" and a.order_id == order_id]

    def refunds(self, order_id: str) -> list[Applied]:
        return [a for a in self.applied.values() if a.kind == "refund" and a.order_id == order_id]

    def _next_fault(self, kind: str, key: str) -> str:
        if self.faults:
            return self.faults.popleft()
        if self.choose_fault is not None:
            return self.choose_fault(kind, key)
        return "ok"

    def _hook(self, phase: str):
        if self.during is None or self._in_hook:
            return
        self._in_hook = True
        try:
            self.during(phase)
        finally:
            self._in_hook = False

    def _execute(self, kind, key, customer, order_id, amount) -> Applied:
        self.calls += 1
        fault = self._next_fault(kind, key)
        if fault not in FAULTS:
            raise ValueError(f"unknown fault {fault!r}")
        self._hook("before")
        if fault == "lost_before":
            raise PaymentTimeout(key)
        if key in self.applied:
            result = self.applied[key]
        elif key in self.declined:
            result = None
        elif fault == "declined":
            self.declined.add(key)
            result = None
        else:
            result = Applied(key=key, kind=kind, customer=customer, order_id=order_id,
                             amount=amount, at=self.clock.now)
            self.applied[key] = result
        self._hook("after")
        if fault == "lost_after":
            raise PaymentTimeout(key)
        if result is None:
            raise PaymentDeclined(key)
        return result
