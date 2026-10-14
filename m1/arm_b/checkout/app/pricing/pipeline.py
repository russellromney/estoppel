"""Run the pricing rules through the stages in composition.py."""

from checkout.app.config import PRICES
from checkout.app.items import Cart
from checkout.app.pricing.composition import STAGES
from checkout.app.pricing.rules import RULES
from checkout.app.pricing.types import Context, Rule, Stage
from checkout.core.api import Adjustment, Line, Quote


class CompositionError(Exception):
    pass


def list_price_quote(cart: Cart) -> Quote:
    return Quote(lines=tuple(Line(sku=sku, qty=qty, unit_price=PRICES[sku]) for sku, qty in cart))


def quote(cart: Cart, context: Context, rules: tuple[Rule, ...] = RULES,
          stages: tuple[Stage, ...] = STAGES) -> Quote:
    unknown = {rule.stage for rule in rules} - {stage.name for stage in stages}
    if unknown:
        raise CompositionError(f"rules use undeclared stages {sorted(unknown)}")
    current = list_price_quote(cart)
    for stage in stages:
        applied = []
        for rule in rules:
            if rule.stage != stage.name:
                continue
            per_line = rule.apply(cart, current, context)
            if per_line is not None and any(per_line):
                applied.append(Adjustment(rule=rule.name, per_line=tuple(per_line)))
        current = Quote(lines=current.lines, adjustments=current.adjustments + stack(stage, applied))
    return current


def stack(stage: Stage, applied: list[Adjustment]) -> tuple[Adjustment, ...]:
    if stage.stacking == "all" or len(applied) <= 1:
        return tuple(applied)
    if stage.stacking == "best":
        return (min(applied, key=lambda a: a.amount),)
    raise CompositionError(f"rules {[a.rule for a in applied]} both apply "
                           f"in exclusive stage {stage.name}")
