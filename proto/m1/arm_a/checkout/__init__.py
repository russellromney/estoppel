"""Checkout service (M1 arm A: conventional design)."""

from checkout.config import INITIAL_STOCK, PRICES
from checkout.gateway import PaymentGateway
from checkout.service import CheckoutService
from checkout.store import Store


def build(clock, provider) -> CheckoutService:
    return CheckoutService(Store(PRICES, INITIAL_STOCK), PaymentGateway(provider), clock)
