"""The active pricing rules. A rule is activated by adding it here. Its stage must be one of
the stages in composition.py, and the stage's stacking policy decides how it combines."""

from checkout.app.pricing.rules.b2g1 import B2G1
from checkout.app.pricing.rules.save10 import SAVE10
from checkout.app.pricing.types import Rule

RULES: tuple[Rule, ...] = (B2G1, SAVE10)
