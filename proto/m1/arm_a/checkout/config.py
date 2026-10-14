"""Catalog and policy settings."""

PRICES = {"A": 1000, "B": 2500, "C": 400, "D": 9900}  # cents
INITIAL_STOCK = 6

HOLD_SECONDS = 900                  # how long a reservation holds stock
REFUND_WINDOW_SECONDS = 30 * 86_400  # measured from the provider's charge time
