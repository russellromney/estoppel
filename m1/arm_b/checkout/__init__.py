"""Checkout service (M1 arm B: a core that decides, and a periphery that proposes)."""

from checkout.app.config import INITIAL_STOCK, PRICES
from checkout.app.service import CheckoutService
from checkout.core.api import Runtime


def build(clock, provider) -> CheckoutService:
    return CheckoutService(Runtime(clock, provider, stock={sku: INITIAL_STOCK for sku in PRICES}))
