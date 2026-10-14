import os
import subprocess
import sys

from checks import planner_props
from app.runtime import default_bindings, load_planner
from sim import dst


def test_same_seed_same_trace():
    assert dst.run(7).trace_hash == dst.run(7).trace_hash
    assert dst.run(7).trace_hash != dst.run(8).trace_hash


def test_trace_independent_of_hash_seed():
    code = "from sim import dst; print(dst.run(3).trace_hash)"
    hashes = set()
    for hs in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=hs)
        out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True,
                             text=True, check=True, cwd=os.path.dirname(os.path.dirname(__file__)))
        hashes.add(out.stdout.strip())
    assert len(hashes) == 1


def test_correct_system_has_no_violations():
    for seed in range(100):
        r = dst.run(seed)
        assert not r.safety, (seed, r.safety)
        assert not r.progress, (seed, r.progress)


def test_v1_planners_satisfy_their_properties():
    for kind, name in default_bindings().items():
        assert planner_props.run(kind, load_planner(name)) == {}, name
