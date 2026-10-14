import pytest
from core_sim import CoreSimulation

pytestmark = pytest.mark.t3

SEEDS = range(300)
STEPS = 200


@pytest.mark.parametrize("seed", SEEDS)
def test_generated_plans_with_faults_and_interleavings(seed):
    CoreSimulation(seed, STEPS).run()


def test_simulations_exercise_both_acceptance_and_refusal():
    sims = [CoreSimulation(seed, STEPS).run() for seed in range(5)]
    applied = [a.kind for s in sims for a in s.provider.applied.values()]
    assert applied.count("charge") >= 30 and applied.count("refund") >= 10
    assert sum(s.refused for s in sims) >= 100


def test_same_seed_same_outcome():
    a, b = CoreSimulation(11, STEPS).run(), CoreSimulation(11, STEPS).run()
    assert a.runtime._state == b.runtime._state
    assert a.provider.applied == b.provider.applied
