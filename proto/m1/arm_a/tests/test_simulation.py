import pytest

from simulation import Simulation

pytestmark = pytest.mark.t3

SEEDS = range(300)
STEPS = 200


@pytest.mark.parametrize("seed", SEEDS)
def test_concurrent_traffic_with_faults(seed):
    Simulation(seed, STEPS).run()


def test_same_seed_same_outcome():
    a, b = Simulation(11, STEPS).run(), Simulation(11, STEPS).run()
    assert a.service.orders() == b.service.orders()
    assert a.provider.applied == b.provider.applied
