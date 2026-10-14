"""Types for pricing rules and their composition."""

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict

from checkout.app.items import Cart
from checkout.core.api import Quote


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class Context(Frozen):
    """Facts about the request that rules may use."""

    customer: str
    coupon: str | None = None   # a known coupon code; the workflow rejects unknown ones


class Rule(Frozen):
    """A pricing rule. `apply` is pure: it returns an amount per quote line (negative is a
    discount), or None when the rule does not apply. It sees the quote as it was when its
    stage began, so rules in one stage do not see each other."""

    name: str
    stage: str
    apply: Callable[[Cart, Quote, Context], tuple[int, ...] | None]


class Stage(Frozen):
    """A step of the pipeline. Stacking says what happens when several of its rules apply:
    all: every one applies
    best: only the largest discount applies (the first registered wins a tie)
    exclusive: at most one may apply; two at once is an error"""

    name: str
    stacking: Literal["all", "best", "exclusive"]


class Property(Frozen):
    """A property every quote must have, checked over small carts and every subset of rules."""

    name: str
    holds: Callable[[Cart, Quote], bool]
