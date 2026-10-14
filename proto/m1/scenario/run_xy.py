"""Replay the scenario's first combine: X (`b2g1`) and Y (`category_windows`), in both arms.

Each change is made in its own git worktree from the scenario base. Its files are copied from
`changes/<step>/`; then it is gated and committed with the commands an agent runs. Then the
changes are combined. Every command is logged with its exit code, CPU and wall time, and the
checks it ran.

    uv run python m1/scenario/run_xy.py WORKTREE_DIR        # from proto/

The `scn/*` branches and the worktrees are recreated on every run. Results go to `results/`.

The base predates the rename of `newci` to estoppel, so the worktrees run the tool as `../newci`.
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
CHANGES = HERE / "changes"
RESULTS = HERE / "results"
BASE = "138f921"   # base claims (ccdba17), plus two fixes to newci (df77607, 138f921)
ENV = {"UV_PROJECT_ENVIRONMENT": str(PROTO / ".venv"), "UV_FROZEN": "1"}

STEPS = {
    "a": {
        "x": [("a-x", "b2g1: every third unit of a SKU is free", None)],
        "y": [("a-y", "category_windows: refund windows by product category", None)],
    },
    "b": {
        "x": [("b-x-publish", "b2g1: publish the rule", "publish"),
              ("b-x-activate", "b2g1: activate the rule", "activate")],
        "y": [("b-y-publish", "category_windows: publish windows by category", "publish"),
              ("b-y-modify", "category_windows: use them in the refund policy", "modify")],
    },
}


# Edits that change only a module-level value, made on the combined tree and then undone. A check
# that reads such a value runs no line of its module, so line coverage does not see the module.
PROBES = {
    "a": [("config", "checkout/config.py", r"^REFUND_WINDOW_SECONDS = .*$", "REFUND_WINDOW_SECONDS = 1")],
    "b": [("config", "checkout/app/config.py", r"^REFUND_WINDOW_SECONDS = .*$", "REFUND_WINDOW_SECONDS = 1"),
          ("binding", "checkout/app/pricing/rules/__init__.py", r"^RULES: .*$",
           "RULES: tuple[Rule, ...] = ()")],
}


class Log:
    def __init__(self):
        self.entries: list[dict] = []
        self.out = RESULTS / "xy-logs"
        shutil.rmtree(self.out, ignore_errors=True)
        self.out.mkdir(parents=True)

    def run(self, step: str, role: str, command: str, cwd: Path, root: Path, ok=(0,), **extra):
        """role: agent, integrator, measure (a measurement only) or audit."""
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
        (self.out / f"{entry['n']:02}-{step}.txt").write_text(
            f"$ {command}\n(cwd {entry['cwd']}, exit {proc.returncode})\n\n{proc.stdout}{proc.stderr}")
        counts = {k: int(n) for n, k in re.findall(r"(\d+) (passed|failed|deselected)", proc.stdout)}
        if counts:
            entry["pytest"] = counts
        if proc.returncode not in ok:
            sys.exit(f"step {step}: `{command}` exited {proc.returncode}\n{proc.stdout}{proc.stderr}")
        return entry, proc


def git(*args, cwd=PROTO) -> str:
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


RAN: dict[int, list[str]] = {}     # log entry -> the checks it ran, to weigh them after the audit


def weigh(entries, arm: str, times: dict[str, float]):
    """Each run's share of the full suite's check time, timed without testmon's tracing."""
    total = sum(times.values())
    for e in entries:
        if e["n"] in RAN and (e["step"] == f"base-{arm}" or e["step"].startswith(f"{arm}-")):
            ran = RAN.pop(e["n"])
            e["share"] = round(sum(times.get(c, 0) for c in ran) / total, 4)
            e["unmatched"] = sum(c not in times for c in ran)


def apply(step: str, worktree: Path):
    src = CHANGES / step
    for f in sorted(p for p in src.rglob("*") if p.is_file()):
        dest = worktree / "m1" / f.relative_to(src)
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
    xml = RESULTS / "xy-logs" / f"junit-{step}-{label}.xml"
    entry, _ = log.run(step, role, f"uv run pytest --testmon -q --junitxml={xml}", arm_dir, root,
                       ok=ok, gate="testmon", data=label)
    ran = junit_tests(xml)
    xml.unlink()
    RAN[entry["n"]] = [c for c, _ in ran]
    entry.update(ran=len(ran), ran_by_tier=by_tier([module(c) for c, _ in ran], tiers(arm_dir)),
                 check_seconds=round(sum(t for _, t in ran), 2))
    return entry


def probe(log, arm, arm_dir, wt):
    """Does each gate rerun the checks that a value-only edit breaks? The full suite says which do."""
    for name, file, pattern, line in PROBES[arm]:
        path = arm_dir / file
        text = path.read_text()
        edited = re.sub(pattern, line, text, count=1, flags=re.M)
        assert edited != text, (arm, name)
        path.write_text(edited)
        step = f"{arm}-probe-{name}"
        testmon(log, step, "probe", arm_dir, wt, None, "int", ok=(0, 1, 5))
        if arm == "b":
            log.run(step, "probe", "uv run python ../newci gate", arm_dir, wt, ok=(0, 1), gate="newci")
        log.run(step, "probe", "uv run pytest -q -p no:cacheprovider --tb=line", arm_dir, wt, ok=(0, 1))
        git("checkout", "--", ".", cwd=arm_dir)
        git("clean", "-fq", "--", ".newci", cwd=arm_dir)
        assert not git("status", "--porcelain", "--", ".", cwd=arm_dir).strip()


def lines_changed(arm: str, ref: str) -> dict[str, int]:
    out = Counter()
    # The base predates the move of the repository root above proto/, hence `:(top)`.
    for line in git("diff", "--numstat", f"{BASE}..{ref}", "--", f":(top)m1/arm_{arm}").splitlines():
        added, removed, path = line.split("\t")
        if added == "-":
            continue
        n = int(added) + int(removed)
        if "/.newci/" in path:
            area = "claims (files)"
            n = 1
        elif "/tests/" in path:
            area = "tests"
        elif arm == "b" and "/checkout/core/" in path:
            area = "core"
        elif arm == "a" and path.rsplit("/", 1)[-1] in ("service.py", "store.py", "models.py", "gateway.py"):
            area = "shared"
        else:
            area = "periphery" if arm == "b" else "rules and policies"
        out[area] += n
    return dict(out)


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
        arm_dir = wt / "m1" / f"arm_{arm}"
        testmon(log, f"base-{arm}", "measure", arm_dir, wt, None, "none")
        copy_db(arm_dir / ".testmondata", data / f"{arm}-base")

    results = {"base": base, "steps": {}}
    for arm in "ab":
        for change in ("x", "y"):
            branch = f"scn/{arm}-{change}"
            wt = worktree(f"{arm}-{change}", branch)
            arm_dir = wt / "m1" / f"arm_{arm}"
            copy_db(data / f"{arm}-base", arm_dir / ".testmondata")
            for step, message, kind in STEPS[arm][change]:
                apply(step, wt)
                if arm == "a":
                    testmon(log, step, "agent", arm_dir, wt, None, "branch")
                    log.run(step, "agent", f'git add -A && git commit -q -m "{message}"', arm_dir, wt)
                else:
                    before = set(p.name for p in (arm_dir / ".newci" / "claims").glob("*.jsonl"))
                    entry, _ = log.run(step, "agent", f"uv run python ../newci gate --kind {kind}",
                                       arm_dir, wt, gate="newci")
                    stdout = (log.out / f"{entry['n']:02}-{step}.txt").read_text()
                    m = re.search(r"checks: (\d+) kept by valid claims; (\d+) ran", stdout)
                    entry.update(kept=int(m.group(1)), ran=int(m.group(2)))
                    new = set(p.name for p in (arm_dir / ".newci" / "claims").glob("*.jsonl")) - before
                    claims = [json.loads(line) for name in new
                              for line in (arm_dir / ".newci/claims" / name).read_text().splitlines()]
                    RAN[entry["n"]] = [check_name(c["test"]) for c in claims]
                    entry.update(ran_by_tier=by_tier(map(module, RAN[entry["n"]]), tiers(arm_dir)),
                                 check_seconds=round(sum(c["seconds"] for c in claims), 2),
                                 change=re.search(r"change: (.*)", stdout).group(1))
                    if kind == "modify":
                        # Could the agent have declared it an activate instead? The gate refuses
                        # before running any check.
                        log.run(step, "probe", "uv run python ../newci gate --kind activate",
                                arm_dir, wt, ok=(2,))
                    testmon(log, step, "measure", arm_dir, wt, None, "branch")
                    log.run(step, "agent",
                            f'git add -A && git commit -q -m "{message}" -m "Newci-Kind: {kind}"',
                            arm_dir, wt)
            copy_db(arm_dir / ".testmondata", data / f"{arm}-{change}")
            results["steps"][branch] = lines_changed(arm, branch)

        # Combine X and Y.
        step = f"{arm}-combine"
        branch = f"scn/{arm}-int"
        wt = worktree(f"{arm}-int", branch)
        arm_dir = wt / "m1" / f"arm_{arm}"
        if arm == "a":
            log.run(step, "integrator", "git merge -q --no-edit scn/a-x scn/a-y", arm_dir, wt)
            testmon(log, step, "integrator", arm_dir, wt, data / "a-base", "base")
        else:
            report = RESULTS / "xy-combine-b.json"
            entry, _ = log.run(step, "integrator",
                               f"uv run python ../newci combine scn/b-x scn/b-y --report {report}",
                               arm_dir, wt, gate="newci")
            r = json.loads(report.read_text())
            ran = [check_name(t) for t in r["result"]["ran"]]
            RAN[entry["n"]] = ran
            new = r["result"]["claims_file"]
            claims = [json.loads(line) for line in
                      (arm_dir / ".newci/claims" / new).read_text().splitlines()]
            entry.update(kept=sum(r["kept"].values()), kept_from=r["kept"], ran=len(ran),
                         ran_by_tier=by_tier(map(module, ran), tiers(arm_dir)), recheck=sorted(r["recheck"]),
                         check_seconds=round(sum(c["seconds"] for c in claims), 2))
            testmon(log, step, "measure", arm_dir, wt, data / "b-base", "base")
        testmon(log, step, "measure", arm_dir, wt, data / f"{arm}-x", "x")

        # Audit: the arm's full suite, and the acceptance suite with both features.
        xml = RESULTS / "xy-logs" / f"junit-{step}-audit.xml"
        entry, _ = log.run(step, "audit", f"uv run pytest -q -p no:cacheprovider --junitxml={xml}",
                           arm_dir, wt)
        everything = dict(junit_tests(xml))
        xml.unlink()
        entry.update(check_seconds=round(sum(everything.values()), 2))
        weigh(log.entries, arm, everything)
        probe(log, arm, arm_dir, wt)
        log.run(step, "audit", f"uv run pytest acceptance --arm {arm} "
                f"--features b2g1,category_windows -q -p no:cacheprovider", wt / "m1", wt)
        results["steps"][branch] = lines_changed(arm, branch)

    results["log"] = log.entries
    (RESULTS / "xy.json").write_text(json.dumps(results, indent=1))
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
    return "\n".join(rows)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
