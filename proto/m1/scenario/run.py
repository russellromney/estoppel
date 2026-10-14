"""Replay the scenario in both arms: X (`b2g1`) and Y (`category_windows`) combined, then Z
(`coupons`) combined with X+Y.

Each change is made in its own git worktree from the scenario base. Its files are copied from
`changes/<step>/`; then it is gated and committed with the commands an agent runs. Then the
changes are combined. Where git or estoppel stops, the resolution's files are copied from
`changes/<arm>-z-resolve/`. Every command is logged with its exit code, CPU and wall time, and
the checks it ran.

    uv run python m1/scenario/run.py WORKTREE_DIR        # from proto/

The `scn/*` branches and the worktrees are recreated on every run. Results go to `results/`.

The X+Y results in RESULTS.md came from an earlier version of this script, `run_xy.py`, at
commit 2329589, against an earlier base.
"""

import json
import os
import re
import resource
import shutil
import sqlite3
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTO = HERE.parent.parent
REPO = PROTO.parent
CHANGES = HERE / "changes"
RESULTS = HERE / "results"
LOGS = RESULTS / "run-logs"
BASE = "565f4a8"   # base claims under estoppel (b80dc76), plus `combine --resolved`
ENV = {"UV_PROJECT_ENVIRONMENT": str(PROTO / ".venv"), "UV_FROZEN": "1"}

STEPS = {
    "a": {
        "x": [("a-x", "b2g1: every third unit of a SKU is free", None)],
        "y": [("a-y", "category_windows: refund windows by product category", None)],
        "z": [("a-z", "coupons: SAVE10, with a shared redemption limit", None)],
    },
    "b": {
        "x": [("b-x-publish", "b2g1: publish the rule", "publish"),
              ("b-x-activate", "b2g1: activate the rule", "activate")],
        "y": [("b-y-publish", "category_windows: publish windows by category", "publish"),
              ("b-y-modify", "category_windows: use them in the refund policy", "modify")],
        "z": [("b-z-core", "coupons: budgets in the core", "modify"),
              ("b-z-periphery", "coupons: codes in the place-order workflow", "modify"),
              ("b-z-publish", "coupons: publish the SAVE10 rule", "publish"),
              ("b-z-activate", "coupons: activate SAVE10 in a new order stage", "activate")],
    },
}

DECISION = ("Keep both rules. SAVE10 is in the order stage, which runs after the item stage, so it "
            "takes 10% off the price after b2g1's free units: three A with SAVE10 cost 1800, not "
            "1700. Agreed for X (b2g1) and Z (coupons).")


# Edits that change only a module-level value, made on the combined tree and then undone. A check
# that reads such a value runs no line of its module, so line coverage does not see the module.
PROBES = {
    "a": [("config", "checkout/config.py", r"^REFUND_WINDOW_SECONDS = .*$", "REFUND_WINDOW_SECONDS = 1"),
          ("coupons", "checkout/config.py", r"^COUPONS = .*$", 'COUPONS = {"SAVE10": 1}')],
    "b": [("config", "checkout/app/config.py", r"^REFUND_WINDOW_SECONDS = .*$", "REFUND_WINDOW_SECONDS = 1"),
          ("binding", "checkout/app/pricing/rules/__init__.py", r"^RULES: .*$",
           "RULES: tuple[Rule, ...] = ()"),
          ("coupons", "checkout/app/config.py", r"^COUPONS = .*$",
           'COUPONS = MappingProxyType({"SAVE10": 1})')],
}


class Log:
    def __init__(self):
        self.entries: list[dict] = []
        shutil.rmtree(LOGS, ignore_errors=True)
        LOGS.mkdir(parents=True)

    def path(self, entry) -> Path:
        return LOGS / f"{entry['n']:03}-{entry['step']}.txt"

    def run(self, step: str, role: str, command: str, cwd: Path, root: Path, ok=(0,), **extra):
        """role: agent, integrator, measure (a measurement only), probe or audit."""
        env = {**os.environ, **ENV}
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = time.perf_counter()
        proc = subprocess.run(command, shell=True, cwd=cwd, env=env, capture_output=True, text=True)
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        entry = {
            "n": len(self.entries) + 1, "step": step, "role": role, "command": command,
            "cwd": cwd.relative_to(root).as_posix(), "exit": proc.returncode,
            "cpu": round(after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime, 2),
            "wall": round(time.perf_counter() - start, 2), **extra,
        }
        self.entries.append(entry)
        self.path(entry).write_text(
            f"$ {command}\n(cwd {entry['cwd']}, exit {proc.returncode})\n\n{proc.stdout}{proc.stderr}")
        counts = {k: int(n) for n, k in re.findall(r"(\d+) (passed|failed|deselected)", proc.stdout)}
        if counts:
            entry["pytest"] = counts
        if proc.returncode not in ok:
            sys.exit(f"step {step}: `{command}` exited {proc.returncode}\n{proc.stdout}{proc.stderr}")
        return entry, proc


def git(*args, cwd=REPO) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True).stdout


def tiers(arm_dir: Path) -> dict[str, str]:
    out = {}
    for path in (arm_dir / "tests").glob("test_*.py"):
        m = re.search(r"pytestmark = pytest\.mark\.(t\d)", path.read_text())
        out[path.stem] = m.group(1) if m else "?"
    return out


def by_tier(tests, tier_of) -> dict[str, int]:
    return dict(sorted(Counter(tier_of.get(t, "?") for t in tests).items()))


def junit_tests(path: Path) -> list[tuple[str, float]]:
    """(check, seconds) for each check that ran. Seconds are wall time, per pytest."""
    root = ET.parse(path).getroot()
    return [(f"{case.get('classname').split('.')[-1]}::{case.get('name')}", float(case.get("time")))
            for case in root.iter("testcase") if case.find("skipped") is None]


def check_name(test_id: str) -> str:
    """`tests/test_x.py::name` as `test_x::name`, as junit_tests names it."""
    file, _, name = test_id.partition("::")
    return f"{file.rsplit('/', 1)[-1][:-3]}::{name}"


def module(check: str) -> str:
    return check.split("::")[0]


RAN: dict[int, list[str]] = {}     # log entry -> the checks it ran, to weigh them after an audit


def weigh(entries, arm: str, times: dict[str, float]):
    """Each run's share of the full suite's check time, timed without testmon's tracing. Weighs
    the runs not yet weighed, against the suite at the latest audit."""
    total = sum(times.values())
    for e in entries:
        if e["n"] in RAN and (e["step"] == f"base-{arm}" or e["step"].startswith(f"{arm}-")):
            ran = RAN.pop(e["n"])
            e["share"] = round(sum(times.get(c, 0) for c in ran) / total, 4)
            e["unmatched"] = sum(c not in times for c in ran)


def apply(step: str, worktree: Path):
    src = CHANGES / step
    for f in sorted(p for p in src.rglob("*") if p.is_file()):
        dest = worktree / "proto" / "m1" / f.relative_to(src)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, dest)


def copy_db(src: Path, dest: Path):
    """Copy a testmon database. Testmon writes in WAL mode, so a plain file copy can miss data."""
    for stale in dest.parent.glob(dest.name + "*"):
        stale.unlink()
    with sqlite3.connect(src) as a, sqlite3.connect(dest) as b:
        a.backup(b)
    a.close()
    b.close()


def testmon(log, step, role, arm_dir, root, data: Path | None, label, ok=(0,)):
    """Run pytest --testmon, starting from `data` if given. Counts the checks it ran."""
    if data is not None:
        copy_db(data, arm_dir / ".testmondata")
    xml = LOGS / f"junit-{step}-{label}.xml"
    entry, _ = log.run(step, role, f"uv run pytest --testmon -q --junitxml={xml}", arm_dir, root,
                       ok=ok, gate="testmon", data=label)
    ran = junit_tests(xml)
    xml.unlink()
    if role != "probe":
        RAN[entry["n"]] = [c for c, _ in ran]
    entry.update(ran=len(ran), ran_by_tier=by_tier([module(c) for c, _ in ran], tiers(arm_dir)),
                 check_seconds=round(sum(t for _, t in ran), 2))
    return entry


def gate(log, step, arm_dir, wt, kind):
    """`estoppel gate --kind K`, with the checks it ran and the claims it wrote."""
    before = set(p.name for p in (arm_dir / ".estoppel" / "claims").glob("*.jsonl"))
    entry, _ = log.run(step, "agent", f"uv run python ../estoppel gate --kind {kind}",
                       arm_dir, wt, gate="estoppel")
    stdout = log.path(entry).read_text()
    m = re.search(r"checks: (\d+) kept by valid claims; (\d+) ran", stdout)
    entry.update(kept=int(m.group(1)), ran=int(m.group(2)))
    new = set(p.name for p in (arm_dir / ".estoppel" / "claims").glob("*.jsonl")) - before
    claims = [json.loads(line) for name in new
              for line in (arm_dir / ".estoppel/claims" / name).read_text().splitlines()]
    RAN[entry["n"]] = [check_name(c["test"]) for c in claims]
    entry.update(ran_by_tier=by_tier(map(module, RAN[entry["n"]]), tiers(arm_dir)),
                 check_seconds=round(sum(c["seconds"] for c in claims), 2),
                 change=re.search(r"change: (.*)", stdout).group(1))
    return entry


def combined(log, entry, arm_dir, report: Path):
    """Record what an `estoppel combine` that committed kept and ran."""
    r = json.loads(report.read_text())
    ran = [check_name(t) for t in r["result"]["ran"]]
    RAN[entry["n"]] = ran
    claims = [json.loads(line) for line in
              (arm_dir / ".estoppel/claims" / r["result"]["claims_file"]).read_text().splitlines()]
    entry.update(kept=sum(r["kept"].values()), kept_from=r["kept"], ran=len(ran),
                 ran_by_tier=by_tier(map(module, ran), tiers(arm_dir)), recheck=sorted(r["recheck"]),
                 check_seconds=round(sum(c["seconds"] for c in claims), 2),
                 interacting=r["bindings_used_by_other_side"], joint=r["joint"])


def conflicts(wt: Path) -> list[str]:
    return git("diff", "--name-only", "--diff-filter=U", cwd=wt).split()


def probe(log, arm, arm_dir, wt, prefix, names):
    """Does each gate rerun the checks that a value-only edit breaks? The full suite says which do."""
    for name, file, pattern, line in PROBES[arm]:
        if name not in names:
            continue
        path = arm_dir / file
        text = path.read_text()
        edited = re.sub(pattern, line, text, count=1, flags=re.M)
        assert edited != text, (arm, name)
        path.write_text(edited)
        step = f"{prefix}-probe-{name}"
        testmon(log, step, "probe", arm_dir, wt, None, "int", ok=(0, 1, 5))
        if arm == "b":
            log.run(step, "probe", "uv run python ../estoppel gate", arm_dir, wt, ok=(0, 1),
                    gate="estoppel")
        log.run(step, "probe", "uv run pytest -q -p no:cacheprovider --tb=line", arm_dir, wt, ok=(0, 1))
        git("checkout", "--", ".", cwd=arm_dir)
        git("clean", "-fq", "--", ".estoppel", cwd=arm_dir)
        assert not git("status", "--porcelain", "--", ".", cwd=arm_dir).strip()


def audit(log, step, arm, arm_dir, wt, features):
    """The arm's full suite, which weighs every run so far, and the acceptance suite."""
    xml = LOGS / f"junit-{step}-audit.xml"
    entry, _ = log.run(step, "audit", f"uv run pytest -q -p no:cacheprovider --junitxml={xml}",
                       arm_dir, wt)
    everything = dict(junit_tests(xml))
    xml.unlink()
    entry.update(check_seconds=round(sum(everything.values()), 2), checks=len(everything))
    weigh(log.entries, arm, everything)
    log.run(step, "audit", f"uv run pytest acceptance --arm {arm} --features {features} -q "
            "-p no:cacheprovider", wt / "proto" / "m1", wt)


def lines_changed(arm: str, ref: str) -> dict[str, int]:
    out = Counter()
    for line in git("diff", "--numstat", f"{BASE}..{ref}", "--", f"proto/m1/arm_{arm}").splitlines():
        added, removed, path = line.split("\t")
        if added == "-":
            continue
        n = int(added) + int(removed)
        name = path.rsplit("/", 1)[-1]
        if "/.estoppel/" in path:
            area = "claims (files)"
            n = 1
        elif arm == "b" and "/tests/" in path and name.startswith(("core_", "test_core_")):
            area = "core tests"
        elif "/tests/" in path:
            area = "tests"
        elif arm == "b" and "/checkout/core/" in path:
            area = "core"
        elif arm == "a" and name in ("service.py", "store.py", "models.py", "gateway.py"):
            area = "shared"
        else:
            area = "periphery" if arm == "b" else "rules and policies"
        out[area] += n
    return dict(out)


def make_change(log, arm, change, wt, data):
    """Make one change on its branch, commit by commit, with the agent's commands."""
    arm_dir = wt / "proto" / "m1" / f"arm_{arm}"
    copy_db(data / f"{arm}-base", arm_dir / ".testmondata")
    for step, message, kind in STEPS[arm][change]:
        apply(step, wt)
        if arm == "a":
            testmon(log, step, "agent", arm_dir, wt, None, "branch")
            log.run(step, "agent", f'git add -A && git commit -q -m "{message}"', arm_dir, wt)
            continue
        gate(log, step, arm_dir, wt, kind)
        if kind == "modify":
            # Could the agent have declared it an activate instead? The gate refuses before
            # running any check.
            log.run(step, "probe", "uv run python ../estoppel gate --kind activate", arm_dir, wt,
                    ok=(2,))
        testmon(log, step, "measure", arm_dir, wt, None, "branch")
        log.run(step, "agent",
                f'git add -A && git commit -q -m "{message}" -m "Estoppel-Kind: {kind}"', arm_dir, wt)
    copy_db(arm_dir / ".testmondata", data / f"{arm}-{change}")


def main(worktrees: Path):
    RESULTS.mkdir(exist_ok=True)
    log = Log()
    base = git("rev-parse", BASE).strip()
    for path in git("worktree", "list", "--porcelain").splitlines():
        if path.startswith("worktree ") and Path(path[9:]).resolve().is_relative_to(worktrees.resolve()):
            git("worktree", "remove", "--force", path[9:])
    for branch in git("branch", "--list", "scn/*", "--format=%(refname:short)").split():
        git("branch", "-D", branch)
    shutil.rmtree(worktrees, ignore_errors=True)
    worktrees.mkdir(parents=True)
    data = worktrees / "testmon-data"
    data.mkdir()

    def worktree(name, branch=None):
        path = worktrees / name
        if branch:
            git("worktree", "add", "-q", "-b", branch, str(path), base)
        else:
            git("worktree", "add", "-q", "--detach", str(path), base)
        return path

    # Base testmon data for both arms: a full run at the base, as main's CI would have.
    wt = worktree("base")
    for arm in "ab":
        arm_dir = wt / "proto" / "m1" / f"arm_{arm}"
        testmon(log, f"base-{arm}", "measure", arm_dir, wt, None, "none")
        copy_db(arm_dir / ".testmondata", data / f"{arm}-base")

    results = {"base": base, "steps": {}, "conflicts": {}}
    for arm in "ab":
        for change in ("x", "y"):
            branch = f"scn/{arm}-{change}"
            make_change(log, arm, change, worktree(f"{arm}-{change}", branch), data)
            results["steps"][branch] = lines_changed(arm, branch)

        # Combine X and Y.
        step = f"{arm}-xy-combine"
        wt = worktree(f"{arm}-int", f"scn/{arm}-int")
        arm_dir = wt / "proto" / "m1" / f"arm_{arm}"
        if arm == "a":
            log.run(step, "integrator", "git merge -q --no-edit scn/a-x scn/a-y", arm_dir, wt)
            testmon(log, step, "integrator", arm_dir, wt, data / "a-base", "base")
        else:
            report = RESULTS / "combine-b-xy.json"
            entry, _ = log.run(step, "integrator",
                               f"uv run python ../estoppel combine scn/b-x scn/b-y --report {report}",
                               arm_dir, wt, gate="estoppel")
            combined(log, entry, arm_dir, report)
            testmon(log, step, "measure", arm_dir, wt, data / "b-base", "base")
        copy_db(arm_dir / ".testmondata", data / f"{arm}-int")     # what main's CI now has
        testmon(log, step, "measure", arm_dir, wt, data / f"{arm}-x", "x")
        audit(log, step, arm, arm_dir, wt, "b2g1,category_windows")
        probe(log, arm, arm_dir, wt, f"{arm}-xy", ("config", "binding"))
        results["steps"][f"scn/{arm}-int (X+Y)"] = lines_changed(arm, f"scn/{arm}-int")

        # Z, from the same base.
        branch = f"scn/{arm}-z"
        make_change(log, arm, "z", worktree(f"{arm}-z", branch), data)
        results["steps"][branch] = lines_changed(arm, branch)

        # Combine Z with X+Y. git stops on conflicts, and estoppel may stop first.
        step = f"{arm}-z-combine"
        resolve = f"cp -R {CHANGES / f'{arm}-z-resolve'}/. {wt / 'proto' / 'm1'}/"
        if arm == "a":
            log.run(step, "integrator", "git merge -q --no-edit scn/a-z", arm_dir, wt, ok=(0, 1))
            results["conflicts"][arm] = conflicts(wt)
            log.run(step, "integrator", resolve, arm_dir, wt, edit="resolve")
            log.run(step, "integrator", "git add -A && git commit -q --no-edit", arm_dir, wt)
            testmon(log, step, "integrator", arm_dir, wt, data / "a-int", "int")
        else:
            stop = RESULTS / "combine-b-z-stop.json"
            entry, _ = log.run(step, "integrator",
                               f"uv run python ../estoppel combine scn/b-z --report {stop}",
                               arm_dir, wt, ok=(0, 3), gate="estoppel")
            if entry["exit"] == 0:      # no stop: the combine merged and committed
                combined(log, entry, arm_dir, stop)
                results["conflicts"][arm] = []
            else:
                entry["joint"] = json.loads(stop.read_text())["joint"]
                log.run(step, "integrator", "git merge -q --no-commit scn/b-z", arm_dir, wt,
                        ok=(0, 1))
                results["conflicts"][arm] = conflicts(wt)
                log.run(step, "integrator", resolve, arm_dir, wt, edit="resolve")
                log.run(step, "integrator", "git add -A", arm_dir, wt)
                report = RESULTS / "combine-b-z.json"
                entry, _ = log.run(step, "integrator",
                                   f"uv run python ../estoppel combine scn/b-z --resolved "
                                   f"--decision \"{DECISION}\" --report {report}",
                                   arm_dir, wt, gate="estoppel")
                combined(log, entry, arm_dir, report)
            testmon(log, step, "measure", arm_dir, wt, data / "b-int", "int")
        testmon(log, step, "measure", arm_dir, wt, data / f"{arm}-z", "z")
        audit(log, step, arm, arm_dir, wt, "b2g1,category_windows,coupons")
        probe(log, arm, arm_dir, wt, f"{arm}-z", [name for name, *_ in PROBES[arm]])
        results["steps"][f"scn/{arm}-int (X+Y+Z)"] = lines_changed(arm, f"scn/{arm}-int")

    results["log"] = log.entries
    (RESULTS / "run.json").write_text(json.dumps(results, indent=1))
    (RESULTS / "run-summary.md").write_text(summary(results) + "\n")
    print(summary(results))


def share(e) -> str:
    if "share" not in e:
        return ""
    return f"{e['share']:.1%}" + (f" ({e['unmatched']} unmatched)" if e["unmatched"] else "")


def summary(results) -> str:
    rows = ["| # | Step | Role | Command | Exit | Ran | By tier | Kept | Share | Check s | Pytest | CPU s | Wall s |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for e in results["log"]:
        command = re.sub(r" --junitxml=\S+", "", e["command"]).replace("|", "\\|")
        command = re.sub(r" --report \S+", "", command)
        command = re.sub(r' --decision ".*?"', ' --decision "..."', command)
        if e.get("edit"):
            command = "(copy the resolution's files)"
        if e.get("data") not in (None, "branch", "none"):
            command += f"  (testmon data: {e['data']})"
        tier = ", ".join(f"{k} {v}" for k, v in e.get("ran_by_tier", {}).items())
        counts = ", ".join(f"{v} {k}" for k, v in e.get("pytest", {}).items())
        rows.append(f"| {e['n']} | {e['step']} | {e['role']} | `{command}` | {e['exit']} | "
                    f"{e.get('ran', '')} | {tier} | {e.get('kept', '')} | {share(e)} | {e.get('check_seconds', '')} | "
                    f"{counts} | {e['cpu']} | {e['wall']} |")
    rows += ["", "| Branch | Lines changed by area |", "|---|---|"]
    rows += [f"| {b} | {', '.join(f'{k} {v}' for k, v in sorted(a.items()))} |"
             for b, a in results["steps"].items()]
    rows += ["", "| Arm | Files git could not merge at Z's combine |", "|---|---|"]
    rows += [f"| {arm} | {', '.join(files)} |" for arm, files in results["conflicts"].items()]
    return "\n".join(rows)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
