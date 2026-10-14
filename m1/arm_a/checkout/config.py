"""Catalog and policy settings."""

PRICES = {"A": 1000, "B": 2500, "C": 400, "D": 9900}  # cents
INITIAL_STOCK = 6

HOLD_SECONDS = 900                  # how long a reservation holds stock
REFUND_WINDOW_SECONDS = 30 * 86_400  # measured from the provider's charge time

# Refund windows by product category. An order's window is the shortest among its items.
CATEGORIES = {"A": "general", "B": "general", "C": "food", "D": "electronics"}
CATEGORY_REFUND_WINDOWS = {"general": REFUND_WINDOW_SECONDS, "food": 7 * 86_400,
                           "electronics": 15 * 86_400}
