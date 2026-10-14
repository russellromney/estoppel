"""How pricing rules combine. Every decision about rules interacting is made here.

Editing this file is a joint decision: adding or reordering a stage, changing a stage's
stacking policy, or changing a property affects every rule. Adding a rule to an existing
stage (in rules/__init__.py) does not need an edit here.
"""

from checkout.app.pricing.types import Property, Stage

STAGES = (
    Stage(name="item", stacking="all"),  # promotions on individual SKUs; they all apply
    Stage(name="order", stacking="best"),  # discounts on the whole order, such as coupons; they
                                           # see the price after item promotions, and only the
                                           # largest applies
)

PROPERTIES = (
    Property(name="rules only lower prices",
             holds=lambda cart, quote: all(x <= 0 for a in quote.adjustments for x in a.per_line)),
    Property(name="no line is priced below zero",
             holds=lambda cart, quote: all(total >= 0 for total in quote.line_totals())),
)
