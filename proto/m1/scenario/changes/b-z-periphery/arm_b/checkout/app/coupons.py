"""Coupon codes. Each code has a budget in the core: an order holds one redemption with its stock,
an expired order returns it, and a charged order keeps it."""

from checkout.app.config import COUPONS
from checkout.core.api import Order

PREFIX = "coupon:"


def known_coupon(code) -> bool:
    return isinstance(code, str) and code in COUPONS


def coupon_budget(code: str) -> str:
    return PREFIX + code


def coupon_budgets() -> dict[str, int]:
    return {coupon_budget(code): limit for code, limit in COUPONS.items()}


def coupon_of(order: Order) -> str | None:
    return next((b.removeprefix(PREFIX) for b in order.budgets if b.startswith(PREFIX)), None)
