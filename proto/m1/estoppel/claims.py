"""Claims that a check passed, and the store that holds them.

A claim names a check, the environment it ran in, and its footprint: the hash of every
definition (and file) the check used. A claim is valid wherever its footprint and environment
match the current tree, so any worktree or branch can reuse it.

The store is a directory committed with the code:
    footprints/<key>.json   a footprint, shared by every claim that has it
    claims/<key>.jsonl      the claims written by one run, one per line
Every file is named by a hash of its content, so two branches never write the same file
differently, and git merges stores without conflicts.
"""

import json
import sys
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from estoppel.config import Project
from estoppel.defs import Index, digest

HARNESS = "<harness>"
CHECKER_FILES = ("claims.py", "config.py", "defs.py", "plugin.py")


class Claim(BaseModel):
    test: str           # pytest node id, relative to the directory holding estoppel.toml
    footprint: str
    env: str
    seconds: float      # CPU seconds the check took when the claim was made


def footprint_key(footprint: dict[str, str]) -> str:
    return digest(json.dumps(sorted(footprint.items())))


def environment(project: Project) -> str:
    """Everything every claim depends on as a whole: interpreter, test runner, checker, lock file."""
    import pytest

    here = Path(__file__).parent
    parts = {
        "python": sys.version,
        "pytest": pytest.__version__,
        "checker": digest("".join((here / f).read_text() for f in CHECKER_FILES)),
        "files": {f: file_digest(project.arm / f) for f in project.config.env},
    }
    return digest(json.dumps(parts, sort_keys=True))


def file_digest(path: Path) -> str | None:
    try:
        return digest(path.read_bytes().decode(errors="replace"))
    except OSError:
        return None


class Current:
    """The hash, in the current tree, of anything a footprint can name."""

    def __init__(self, index: Index):
        self.index = index

    def __call__(self, name: str) -> str | None:
        if name == HARNESS:
            return self.index.harness
        if name.startswith("file:"):
            return file_digest(self.index.root / name[len("file:"):])
        d = self.index.defs.get(name)
        return d.hash if d else None


def stale(footprint: dict[str, str], current: Callable[[str], str | None]) -> list[str]:
    return sorted(name for name, h in footprint.items() if current(name) != h)


class Store:
    def __init__(self, directory: Path):
        self.directory = directory
        self._footprints: dict[str, dict[str, str]] = {}
        self._valid: dict[str, bool] = {}

    def load(self) -> dict[str, list[tuple[Claim, str]]]:
        """test -> [(claim, name of the claims file it came from)]"""
        out: dict[str, list[tuple[Claim, str]]] = {}
        for path in sorted((self.directory / "claims").glob("*.jsonl")):
            for line in path.read_text().splitlines():
                claim = Claim.model_validate_json(line)
                out.setdefault(claim.test, []).append((claim, path.name))
        return out

    def footprint(self, key: str) -> dict[str, str]:
        if key not in self._footprints:
            path = self.directory / "footprints" / f"{key}.json"
            self._footprints[key] = json.loads(path.read_text())
        return self._footprints[key]

    def find(self, candidates: list[tuple[Claim, str]], env: str,
             current: Callable[[str], str | None]) -> str | None:
        """The claims file of a valid claim among `candidates`, or None."""
        for claim, source in candidates:
            if claim.env != env:
                continue
            if claim.footprint not in self._valid:
                self._valid[claim.footprint] = not stale(self.footprint(claim.footprint), current)
            if self._valid[claim.footprint]:
                return source
        return None

    def write(self, claims: list[Claim], footprints: dict[str, dict[str, str]]) -> str | None:
        if not claims:
            return None
        (self.directory / "footprints").mkdir(parents=True, exist_ok=True)
        (self.directory / "claims").mkdir(parents=True, exist_ok=True)
        for key, fp in footprints.items():
            path = self.directory / "footprints" / f"{key}.json"
            if not path.exists():
                path.write_text(json.dumps(dict(sorted(fp.items())), indent=0) + "\n")
        text = "".join(c.model_dump_json() + "\n" for c in sorted(claims, key=lambda c: c.test))
        name = f"{digest(text)}.jsonl"
        (self.directory / "claims" / name).write_text(text)
        return name
