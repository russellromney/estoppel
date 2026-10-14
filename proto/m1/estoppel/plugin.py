"""pytest plugin: skip checks that hold a valid claim; record the footprint of each check that
runs, and write a claim for each that passes.

    PYTHONPATH=<parent of estoppel> pytest -p estoppel.plugin --estoppel <directory holding estoppel.toml>

A footprint is recorded at definition granularity:
- every top-level definition with code that started running during the check (sys.monitoring);
- the definitions of the fixtures the check requested, which may have run before it;
- everything those refer to, transitively, except functions that did not run;
- files under the repository root that the check opened;
- the harness: pytest hooks and autouse fixtures in conftest files.
"""

import inspect
import json
import os
import sys
import time
from pathlib import Path

import pytest

from estoppel.claims import HARNESS, Claim, Current, Store, environment, file_digest, footprint_key
from estoppel.config import load
from estoppel.defs import Index

IGNORED_DIRS = {"__pycache__", ".pytest_cache", ".estoppel", ".git"}


def pytest_addoption(parser):
    group = parser.getgroup("estoppel")
    group.addoption("--estoppel", metavar="DIR", help="directory holding estoppel.toml")
    group.addoption("--estoppel-all", action="store_true", help="run every check; still write claims")
    group.addoption("--estoppel-report", metavar="PATH", help="write a JSON summary of the run")


def pytest_configure(config):
    arm = config.getoption("--estoppel")
    if arm:
        config.pluginmanager.register(Session(config, Path(arm)), "estoppel-session")


class Recorder:
    """Records the code objects that start running, and the files opened, while on."""

    def __init__(self):
        mon = sys.monitoring
        free = [t for t in (3, 4) if mon.get_tool(t) is None]
        if not free:
            raise RuntimeError("estoppel: no free sys.monitoring tool id")
        self.tool = free[0]
        mon.use_tool_id(self.tool, "estoppel")
        mon.register_callback(self.tool, mon.events.PY_START, self._started)
        mon.set_events(self.tool, mon.events.PY_START)
        sys.addaudithook(self._audit)
        self.on = False
        self.codes: set = set()
        self.files: set[str] = set()

    def _started(self, code, offset):
        if self.on:
            self.codes.add(code)
        return sys.monitoring.DISABLE   # once per code object, until restart_events()

    def _audit(self, event, args):
        if self.on and event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
            self.files.add(os.fsdecode(args[0]))

    def start(self):
        self.codes, self.files = set(), set()
        sys.monitoring.restart_events()
        self.on = True

    def stop(self):
        self.on = False
        return self.codes, self.files

    def close(self):
        sys.monitoring.set_events(self.tool, 0)
        sys.monitoring.register_callback(self.tool, sys.monitoring.events.PY_START, None)
        sys.monitoring.free_tool_id(self.tool)


class Session:
    def __init__(self, config, arm: Path):
        self.project = load(arm)
        self.index = Index(self.project)
        self.current = Current(self.index)
        self.store = Store(self.project.arm / self.project.config.claims)
        self.env = environment(self.project)
        self.claims = self.store.load()
        self.run_all = config.getoption("--estoppel-all")
        self.report_path = config.getoption("--estoppel-report")
        self.kept: dict[str, str] = {}                      # test -> claims file
        self.ran: dict[str, tuple[str, float]] = {}         # test -> (footprint key, CPU s)
        self.footprints: dict[str, dict[str, str]] = {}
        self.passed: set[str] = set()
        self.failed: set[str] = set()
        self._closures: dict[frozenset, set[str]] = {}
        self.recorder = Recorder()

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, session, config, items):
        run, keep = [], []
        for item in items:
            source = None
            if not self.run_all:
                source = self.store.find(self.claims.get(item.nodeid, []), self.env, self.current)
            if source:
                self.kept[item.nodeid] = source
                keep.append(item)
            else:
                run.append(item)
        if keep:
            items[:] = run
            config.hook.pytest_deselected(items=keep)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(self, item, nextitem):
        start = time.process_time()
        self.recorder.start()
        yield
        codes, files = self.recorder.stop()
        seconds = time.process_time() - start
        fp = self.footprint(item, codes, files)
        key = footprint_key(fp)
        self.footprints[key] = fp
        self.ran[item.nodeid] = (key, seconds)

    def pytest_runtest_logreport(self, report):
        if report.failed:
            self.failed.add(report.nodeid)
        elif report.when == "call" and report.passed:
            self.passed.add(report.nodeid)

    def footprint(self, item, codes, files) -> dict[str, str]:
        index = self.index
        seeds = set()
        for code in codes:
            seeds.update(index.at(code.co_filename, code.co_firstlineno, code.co_name))
        for fixturedefs in item._fixtureinfo.name2fixturedefs.values():
            for fixturedef in fixturedefs:
                code = getattr(inspect.unwrap(fixturedef.func), "__code__", None)
                if code is not None:
                    seeds.update(index.at(code.co_filename, code.co_firstlineno, code.co_name))
        module = index.modules.get(Path(item.path).resolve().relative_to(index.root).as_posix())
        if module is not None:
            seeds.update(module.bound.get("pytestmark", []))
        key = frozenset(seeds)
        if key not in self._closures:
            self._closures[key] = index.closure(seeds)
        fp = {did: index.defs[did].hash for did in self._closures[key]}
        fp[HARNESS] = index.harness
        root = str(index.root) + os.sep
        for name in files:
            real = os.path.realpath(name)
            if not real.startswith(root) or IGNORED_DIRS & set(Path(real).parts):
                continue
            rel = real[len(root):].replace(os.sep, "/")
            if rel not in index.modules:
                fp[f"file:{rel}"] = file_digest(Path(real))
        return fp

    def pytest_terminal_summary(self, terminalreporter):
        cpu = sum(s for _, s in self.ran.values())
        made = len(self.passed - self.failed)
        terminalreporter.write_line(
            f"estoppel: {len(self.kept)} checks kept by valid claims; {len(self.ran)} ran "
            f"({cpu:.2f} s CPU); {made} new claims")

    def pytest_sessionfinish(self, session, exitstatus):
        self.recorder.close()
        passed = {t for t in self.ran if t in self.passed and t not in self.failed}
        claims = [Claim(test=t, footprint=self.ran[t][0], env=self.env, seconds=self.ran[t][1])
                  for t in passed]
        used = {self.ran[t][0] for t in passed}
        written = self.store.write(claims, {k: v for k, v in self.footprints.items() if k in used})
        if self.report_path:
            Path(self.report_path).write_text(json.dumps({
                "kept": self.kept,
                "ran": {t: s for t, (_, s) in self.ran.items()},
                "passed": sorted(passed),
                "failed": sorted(self.failed),
                "claims_file": written,
            }, indent=1, sort_keys=True))
