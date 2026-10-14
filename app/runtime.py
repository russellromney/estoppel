"""Binds request kinds to planner versions and runs the plan step.

Each request pins the configuration that was active when it arrived
(planner name and source hash for every request kind). Phase 0 has a
single configuration; Phase 3 adds activation transactions.
"""

import tomllib
from pathlib import Path
from types import MappingProxyType

from app import restricted

APP_DIR = Path(__file__).parent
PLANNER_DIRS = [APP_DIR / "planners", APP_DIR.parent / "corpus" / "planner_bugs"]


def find_planner(name: str) -> Path:
    for d in PLANNER_DIRS:
        path = d / f"{name}.py"
        if path.exists():
            return path
    raise FileNotFoundError(f"planner {name!r} not found")


def load_planner(name: str) -> restricted.Planner:
    return restricted.load(name, find_planner(name).read_text())


def default_bindings() -> dict[str, str]:
    with open(APP_DIR / "bindings.toml", "rb") as f:
        return dict(tomllib.load(f)["bindings"])


class Runtime:
    def __init__(self, kernel, bindings: dict[str, str] | None = None,
                 planners: dict[str, restricted.Planner] | None = None):
        """`planners` supplies already-loaded planners by name (e.g. mutants)."""
        self.kernel = kernel
        self.bindings = dict(bindings or default_bindings())
        self.planners = dict(planners or {})
        for name in set(self.bindings.values()):
            if name not in self.planners:
                self.planners[name] = load_planner(name)

    def pinned_config(self):
        return MappingProxyType({
            kind: (name, self.planners[name].source_hash)
            for kind, name in sorted(self.bindings.items())
        })

    def snapshot(self, req):
        """Ask the kernel for a snapshot (this issues grants) and freeze it."""
        return restricted.freeze(self.kernel.snapshot(req))

    def propose(self, planner_name: str, req, snapshot) -> dict:
        if planner_name not in self.planners:
            self.planners[planner_name] = load_planner(planner_name)
        planner = self.planners[planner_name]
        public = restricted.freeze({k: v for k, v in req.items() if k != "config"})
        try:
            return restricted.thaw(planner.propose(public, snapshot))
        except Exception as e:  # planner bug: contained, reported as a rejection
            return {"op": "error", "reason": type(e).__name__}

    def plan(self, req) -> tuple[object, dict]:
        snapshot = self.snapshot(req)
        name, _ = req["config"][req["kind"]]
        return snapshot, self.propose(name, req, snapshot)
