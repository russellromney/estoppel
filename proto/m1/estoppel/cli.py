"""Commands. Run them from the directory that holds estoppel.toml.

    python ../estoppel gate [--kind publish|activate|modify] [--all]
        The boundary lint, a check that the working tree's change is the declared kind, then
        every check without a valid claim. Passing checks get claims, to commit with the code.

    python ../estoppel kinds BASE [HEAD]
        Check each commit's declared kind (its `Estoppel-Kind:` trailer) against what it changed.

    python ../estoppel combine BRANCH [BRANCH ...]
        Combine changes made from the same base: check their declared kinds, stop at any
        definition changed differently by more than one of them, merge, report which claims
        are kept and why the rest must rerun, rerun them, and commit the merge.

    python ../estoppel combine BRANCH [BRANCH ...] --resolved --decision TEXT
        Continue after a stop. First merge the branches with git and resolve the definitions
        the stop named, and stage the result. The resolution may change only those definitions.
"""

import argparse
import io
import json
import os
import resource
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from collections import Counter
from pathlib import Path

from estoppel import config as configuration
from estoppel import kinds
from estoppel.claims import Current, Store, environment, file_digest, stale
from estoppel.config import Project
from estoppel.defs import Index, diff

TOOL_PARENT = Path(__file__).resolve().parent.parent


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                          text=True).stdout


def snapshot(project: Project, rev: str) -> tuple[Index, dict[str, str | None]]:
    """The definitions and environment files of `project` at a commit."""
    paths = sorted({project.rel(p) for p in project.config.sources + project.config.env}
                   | {f"{project.arm_rel}/{configuration.FILENAME}"})
    files = [f for f in git(project.root, "ls-tree", "-r", "-z", "--name-only", rev, "--",
                            *paths).split("\0") if f]
    tmp = Path(tempfile.mkdtemp(prefix="estoppel-")).resolve()
    try:
        if files:
            tar = subprocess.run(["git", "archive", "--format=tar", rev, "--", *files],
                                 cwd=project.root, check=True, capture_output=True).stdout
            with tarfile.open(fileobj=io.BytesIO(tar)) as archive:
                archive.extractall(tmp, filter="data")
        arm = tmp / project.arm_rel
        arm.mkdir(parents=True, exist_ok=True)
        if (arm / configuration.FILENAME).exists():
            snap = configuration.load(arm, root=tmp)
        else:
            snap = Project(config=project.config, root=tmp, arm=arm)
        return Index(snap), {f: file_digest(arm / f) for f in snap.config.env}
    finally:
        shutil.rmtree(tmp)


def env_changes(before: dict, after: dict) -> list[str]:
    return sorted(f for f in before.keys() | after.keys() if before.get(f) != after.get(f))


def lint(project: Project) -> bool:
    command = list(project.config.lint)
    if command and command[0] == "python":
        command[0] = sys.executable
    result = subprocess.run(command, cwd=project.arm, capture_output=True, text=True)
    if result.returncode:
        print("lint: failed")
        print(result.stdout + result.stderr)
        return False
    print("lint: ok")
    return True


def run_checks(project: Project, run_all: bool = False) -> dict:
    """Run pytest with the estoppel plugin. Returns the plugin's report, plus CPU and wall time."""
    fd, report = tempfile.mkstemp(suffix=".json", prefix="estoppel-")
    os.close(fd)
    command = [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "estoppel.plugin",
               "--estoppel", str(project.arm), "--estoppel-report", report]
    if run_all:
        command.append("--estoppel-all")
    pythonpath = os.pathsep.join(p for p in (str(TOOL_PARENT), os.environ.get("PYTHONPATH")) if p)
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter()
    proc = subprocess.run(command, cwd=project.arm, env=dict(os.environ, PYTHONPATH=pythonpath))
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    try:
        out = json.loads(Path(report).read_text())
    finally:
        os.unlink(report)
    out["cpu"] = round(after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime, 2)
    out["wall"] = round(time.perf_counter() - start, 2)
    out["ok"] = proc.returncode in (0, 5) and not out["failed"]
    return out


def verify_worktree(project: Project, declared: str) -> kinds.Verdict:
    before, before_env = snapshot(project, "HEAD")
    after = Index(project)
    after_env = {f: file_digest(project.arm / f) for f in project.config.env}
    return kinds.check(declared, before, after, env_changes(before_env, after_env))


def check_commits(project: Project, base: str, head: str) -> list[dict]:
    revs = git(project.root, "rev-list", "--reverse", "--no-merges", f"{base}..{head}").split()
    snaps: dict[str, tuple[Index, dict]] = {}

    def snap(rev):
        if rev not in snaps:
            snaps[rev] = snapshot(project, rev)
        return snaps[rev]

    out = []
    for rev in revs:
        parent = git(project.root, "rev-parse", f"{rev}^").strip()
        subject = git(project.root, "log", "-1", "--format=%s", rev).strip()
        declared = git(project.root, "log", "-1", "--format=%(trailers:key=Estoppel-Kind,valueonly)",
                       rev).strip()
        (before, before_env), (after, after_env) = snap(parent), snap(rev)
        changed_env = env_changes(before_env, after_env)
        if not diff(before, after).touched and not changed_env:
            continue                     # nothing this project tracks
        if not declared:
            verdict = kinds.Verdict(declared="?", ok=False, problems=["no Estoppel-Kind trailer"],
                                    bindings=[], code=[], checks=[], added=0, smallest="modify")
        else:
            verdict = kinds.check(declared, before, after, changed_env)
        out.append({"rev": rev, "subject": subject, "verdict": verdict})
    return out


def print_checks(result: dict) -> None:
    kept = len(result["kept"])
    print(f"checks: {kept} kept by valid claims; {len(result['ran'])} ran; "
          f"{len(result['failed'])} failed; {result['cpu']:.2f} s CPU, {result['wall']:.2f} s wall")


# Commands

def cmd_gate(args) -> int:
    project = configuration.load(configuration.find(Path.cwd()))
    if not lint(project):
        return 1
    if args.kind:
        verdict = verify_worktree(project, args.kind)
        print("change: " + kinds.describe(verdict))
        if not verdict.ok:
            return 2
    result = run_checks(project, run_all=args.all)
    print_checks(result)
    if args.report:
        Path(args.report).write_text(json.dumps(result, indent=1, sort_keys=True))
    if result["ok"] and result.get("claims_file"):
        print(f"claims: wrote {project.config.claims}/claims/{result['claims_file']}; commit it "
              f"with the change (trailer `Estoppel-Kind: {args.kind or '<kind>'}`)")
    return 0 if result["ok"] else 1


def cmd_kinds(args) -> int:
    project = configuration.load(configuration.find(Path.cwd()))
    results = check_commits(project, args.base, args.head)
    for r in results:
        print(f"{r['rev'][:7]} {r['subject'][:50]:50} {kinds.describe(r['verdict'])}")
    return 0 if all(r["verdict"].ok for r in results) else 2


def test_exists(project: Project, index: Index, test: str) -> bool:
    file, _, rest = test.partition("::")
    return f"{project.rel(file)}::{rest.split('::')[0].split('[')[0]}" in index.defs


def check_resolution(project: Project, branches: list[str], base: Index, sides: dict[str, Index],
                     joint: set[str]) -> list[str]:
    """Problems with a merge the agent resolved by hand. Outside the joint definitions, every
    definition must be as on the base or on some side."""
    root = project.root
    merging = subprocess.run(["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"], cwd=root,
                             capture_output=True, text=True)
    if merging.returncode:
        return ["no merge is in progress: run `git merge --no-commit` on the branches first"]
    heads = git(root, "rev-parse", *branches).split()
    merge_heads = Path(git(root, "rev-parse", "--git-path", "MERGE_HEAD").strip())
    if not merge_heads.is_absolute():
        merge_heads = root / merge_heads
    if sorted(merge_heads.read_text().split()) != sorted(heads):
        return ["the merge in progress is not of " + ", ".join(branches)]
    problems = []
    if git(root, "diff", "--name-only", "--diff-filter=U").strip():
        problems.append("some files are still unmerged")
    if git(root, "diff", "--name-only", "--", project.arm_rel).strip():
        problems.append("some changes are not staged")
    merged = Index(project)
    versions = [base, *sides.values()]
    for did in sorted(set(merged.defs).union(*(v.defs for v in versions))):
        mine = merged.defs[did].hash if did in merged.defs else None
        if did in joint:
            continue
        if all(mine != (v.defs[did].hash if did in v.defs else None) for v in versions):
            problems.append(f"{kinds.short(did, project.arm_rel)} differs from the base and every "
                            "side, and was not a joint decision")
    return problems


def cmd_combine(args) -> int:
    project = configuration.load(configuration.find(Path.cwd()))
    root, branches = project.root, args.branches

    def short(did):
        return kinds.short(did, project.arm_rel)

    base = git(root, "merge-base", "--octopus", "HEAD", *branches).strip()
    # The current branch is a side too, when it has changes since the base.
    here = git(root, "rev-parse", "--abbrev-ref", "HEAD").strip()
    ahead = git(root, "rev-parse", "HEAD").strip() != base
    names = ([here] if ahead else []) + list(branches)
    report: dict = {"branches": branches, "sides": names, "base": base}
    print(f"combine {', '.join(branches)} into {here} (base {base[:7]})")

    # 1. Each change is the kind it says it is.
    print("declared kinds:")
    report["kinds"] = {}
    for b in names:
        results = check_commits(project, base, b)
        report["kinds"][b] = [{"rev": r["rev"], "subject": r["subject"],
                               **r["verdict"].model_dump()} for r in results]
        for r in results:
            print(f"  {b} {r['rev'][:7]} {kinds.describe(r['verdict'])}".replace("\n", "\n  "))
        if not all(r["verdict"].ok for r in results):
            print("Stopped: a change is not the kind it declares.")
            return 2

    # 2. Stop at any definition two sides changed differently.
    base_index, _ = snapshot(project, base)
    sides = {b: snapshot(project, b)[0] for b in names}
    diffs = {b: diff(base_index, sides[b]) for b in names}
    joint = []
    for did in sorted(set().union(*(d.touched for d in diffs.values()))):
        who = [b for b in names if did in diffs[b].touched]
        versions = {sides[b].defs[did].hash if did in sides[b].defs else None for b in who}
        if len(who) > 1 and len(versions) > 1:
            binding = base_index.is_binding(did) or any(sides[b].is_binding(did) for b in who)
            joint.append({"definition": did, "binding": binding, "sides": who})
    report["joint"] = joint
    if joint:
        print(("Resolving" if args.resolved else "Stopped:") + " these definitions were changed "
              "differently by more than one side. Each needs a joint decision:")
        for j in joint:
            print(f"  {short(j['definition'])}{' (binding)' if j['binding'] else ''}: "
                  f"{', '.join(j['sides'])}")
        if not args.resolved:
            print("Merge the branches with git, resolve these definitions, stage the result, "
                  "then rerun with --resolved --decision TEXT.")
            return 3
    else:
        print("definitions changed by more than one side: none")

    # 3. Merge, or check the agent's resolution of the merge.
    if args.resolved:
        problems = check_resolution(project, branches, base_index, sides, {j["definition"] for j in joint})
        if joint and not args.decision:
            problems.append("--decision is required: say what was decided, and why")
        if problems:
            print("Stopped: the resolution cannot be used.")
            for p in problems:
                print(f"  {p}")
            return 5
        report["decision"] = args.decision
        print("merge: resolved by hand" + (f"; decision: {args.decision}" if joint else ""))
    else:
        merge = subprocess.run(["git", "merge", "--no-ff", "--no-commit", *branches], cwd=root,
                               capture_output=True, text=True)
        if merge.returncode:
            print("Stopped: git could not merge.\n" + merge.stdout + merge.stderr)
            return 4
        print("merge: clean")

    # 4. Which claims survive, and why the rest do not.
    claims_dir = f"{project.arm_rel}/{project.config.claims}/claims"
    made_on = {}
    for b in names:
        for path in git(root, "diff", "--name-only", "--diff-filter=A", base, b, "--",
                        claims_dir).split():
            made_on[Path(path).name] = b
    merged = Index(project)
    current = Current(merged)
    store = Store(project.arm / project.config.claims)
    claims = store.load()
    env = environment(project)
    kept: Counter = Counter()
    recheck: dict[str, list[str]] = {}
    because: Counter = Counter()
    for test, candidates in sorted(claims.items()):
        if not test_exists(project, merged, test):
            continue
        source = store.find(candidates, env, current)
        if source:
            kept[made_on.get(source, "base")] += 1
            continue
        why = set()
        for claim, _ in candidates:
            why.update(stale(store.footprint(claim.footprint), current) if claim.env == env
                       else ["<environment>"])
        recheck[test] = sorted(why)
        because.update(why)
    used_by_other = Counter()
    for b in names:
        for did in diffs[b].touched:
            if base_index.is_binding(did) or sides[b].is_binding(did):
                for candidates in claims.values():
                    for claim, source in candidates:
                        if made_on.get(source, b) != b and did in store.footprint(claim.footprint):
                            used_by_other[(did, b)] += 1
    report["kept"] = dict(kept)
    report["recheck"] = recheck
    report["bindings_used_by_other_side"] = [
        {"definition": d, "changed_by": b, "claims": n} for (d, b), n in sorted(used_by_other.items())]
    print(f"claims kept: {sum(kept.values())} ("
          + ", ".join(f"{n} made on {o}" for o, n in sorted(kept.items())) + ")")
    print(f"to recheck: {len(recheck)}")
    for name, n in because.most_common():
        who = [b for b in names if name in diffs[b].touched] or ["neither side"]
        print(f"  {n:4} use {short(name)}, changed by {', '.join(who)}")
    for (did, b), n in sorted(used_by_other.items()):
        print(f"  note: binding {short(did)}, changed by {b}, is used by {n} claims made on another side")

    # 5. Recheck, then commit the merge with the new claims.
    if not lint(project):
        return 1
    result = run_checks(project)
    print_checks(result)
    ran = set(result["ran"])
    unexpected = sorted(ran - set(recheck))
    missing = sorted(set(recheck) - ran)
    if unexpected or missing:
        print(f"  ran {len(unexpected)} checks with no claim (new checks), "
              f"and skipped {len(missing)} predicted rechecks")
    report.update(result=result, unexpected=unexpected, missing=missing)
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=1, sort_keys=True))
    if not result["ok"]:
        print("Stopped: a check failed. The merge is not committed.")
        return 1
    subprocess.run(["git", "add", "-A", f"{project.arm_rel}/{project.config.claims}"], cwd=root,
                   check=True)
    message = f"estoppel combine {' '.join(branches)}\n\n"
    if joint:
        message += ("Joint decision on " + ", ".join(short(j["definition"]) for j in joint)
                    + f":\n{args.decision}\n\n")
    message += "Estoppel-Kind: combine\n"
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=root, check=True)
    print(f"committed {git(root, 'rev-parse', '--short', 'HEAD').strip()}")
    if args.report:
        report["commit"] = git(root, "rev-parse", "HEAD").strip()
        Path(args.report).write_text(json.dumps(report, indent=1, sort_keys=True))
    return 0


def main(argv=None) -> int:
    sys.stdout.reconfigure(line_buffering=True)
    parser = argparse.ArgumentParser(prog="estoppel", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    gate = sub.add_parser("gate")
    gate.add_argument("--kind", choices=kinds.KINDS)
    gate.add_argument("--all", action="store_true", help="run every check")
    gate.add_argument("--report", help="write a JSON report here")
    kinds_parser = sub.add_parser("kinds")
    kinds_parser.add_argument("base")
    kinds_parser.add_argument("head", nargs="?", default="HEAD")
    combine = sub.add_parser("combine")
    combine.add_argument("branches", nargs="+")
    combine.add_argument("--report", help="write a JSON report here")
    combine.add_argument("--resolved", action="store_true",
                         help="continue after a stop: the merge has been resolved and staged")
    combine.add_argument("--decision", help="with --resolved: the joint decision, for the record")
    args = parser.parse_args(argv)
    return {"gate": cmd_gate, "kinds": cmd_kinds, "combine": cmd_combine}[args.command](args)
