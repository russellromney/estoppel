import itertools

import pytest
from hypothesis import settings

from checkout import build
from checkout.config import PRICES
from checkout.models import Order, OrderStatus
from world import Clock, Provider

settings.register_profile("ci", derandomize=True, database=None, deadline=None)
settings.load_profile("ci")


@pytest.fixture
def clock():
    return Clock(0)


@pytest.fixture
def provider(clock):
    return Provider(clock)


@pytest.fixture
def service(clock, provider):
    return build(clock, provider)


@pytest.fixture
def rid():
    counter = itertools.count(1)
    return lambda: f"req-{next(counter)}"


@pytest.fixture
def make_order(service, clock):
    """Insert an order directly, holding its stock, without going through place_order."""
    ids = itertools.count(1)

    def make(customer="c1", items=(("A", 1),), status=OrderStatus.RESERVED,
             price=None, reserved_at=None, charged_at=None):
        order = Order(
            id=f"fx-{next(ids)}", customer=customer, items=tuple(items),
            price=price if price is not None else sum(PRICES[s] * q for s, q in items),
            status=status, reserved_at=clock.now if reserved_at is None else reserved_at,
            charged_at=charged_at,
        )
        service.store.take_stock(dict(items))
        service.store.add_order(order)
        return order

    return make
