"""The workflow's configuration, `estoppel.toml`, which lives in the directory of the code it covers."""

import subprocess
import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict

FILENAME = "estoppel.toml"


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: list[str]                   # the import search path, as pytest sets it
    sources: list[str]                # files and directories whose definitions are tracked
    tests: list[str]                  # which of the sources hold checks rather than code
    env: list[str]                    # files that every claim depends on as a whole
    lint: list[str]                   # a command the gate runs before any check
    claims: str = ".estoppel"            # where claims are stored, committed with the code
    bindings: dict[str, list[str]]    # file -> names that select an implementation ("*" = all)


class Project(BaseModel):
    """A configuration, located: `arm` is its directory, `root` the repository root."""

    config: Config
    root: Path
    arm: Path

    def rel(self, path: str) -> str:
        """A path relative to the configuration's directory, as a path from the repository root."""
        return (self.arm / path).resolve().relative_to(self.root.resolve()).as_posix()

    @property
    def arm_rel(self) -> str:
        return self.arm.resolve().relative_to(self.root.resolve()).as_posix()


def load(arm: Path, root: Path | None = None) -> Project:
    arm = arm.resolve()
    config = Config.model_validate(tomllib.loads((arm / FILENAME).read_text()))
    if root is None:
        root = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=arm, check=True,
                                   capture_output=True, text=True).stdout.strip())
    return Project(config=config, root=root.resolve(), arm=arm)


def find(start: Path) -> Path:
    for directory in (start.resolve(), *start.resolve().parents):
        if (directory / FILENAME).exists():
            return directory
    raise SystemExit(f"no {FILENAME} in {start} or its parents")
