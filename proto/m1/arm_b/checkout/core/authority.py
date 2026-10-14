"""Who may propose which moves, on which orders.

Adding a request kind that changes state means adding an entry here.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal

from checkout.core.facts import Fact, Grant, Order


class Entry(Fact):
    principal: Literal["customer", "job", "operator"]
    scope: Literal["new", "subject", "all"]
    moves: frozenset[str]


AUTHORITY: Mapping[str, Entry] = MappingProxyType({
    "place_order": Entry(principal="customer", scope="new", moves=frozenset({"open_order"})),
    "pay": Entry(principal="customer", scope="subject", moves=frozenset({"start_charge"})),
    "refund": Entry(principal="customer", scope="subject", moves=frozenset({"start_refund"})),
    "expire": Entry(principal="job", scope="all", moves=frozenset({"release"})),
    "view": Entry(principal="operator", scope="all", moves=frozenset()),
})


class Unauthorized(Exception):
    pass


def grant(kind: str, principal_type: str, principal: str, subject: str | None,
          orders: Mapping[str, Order]) -> Grant:
    entry = AUTHORITY.get(kind)
    if entry is None or entry.principal != principal_type:
        raise Unauthorized(f"no {principal_type} request kind {kind!r}")
    owned = None
    if entry.scope == "subject" and subject in orders and orders[subject].customer == principal:
        owned = subject
    return Grant(kind=kind, principal=principal, moves=entry.moves, scope=entry.scope, subject=owned)
