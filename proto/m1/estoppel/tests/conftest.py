import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from estoppel.config import load
from estoppel.defs import Index

M1 = Path(__file__).resolve().parents[2]

CONFIG = """
path = ["."]
sources = ["app", "tests"]
tests = ["tests"]
env = ["pytest.ini"]
lint = ["python", "-c", "pass"]
[bindings]
"app/registry.py" = ["ACTIVE"]
"""

PYTEST_INI = "[pytest]\npythonpath = .\ntestpaths = tests\n"


def write(root: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text).lstrip())


@pytest.fixture
def tree(tmp_path):
    """A project directory `proj` inside a repository root, with a writer and an indexer."""
    proj = tmp_path / "proj"
    write(proj, {"estoppel.toml": CONFIG, "pytest.ini": PYTEST_INI, "app/__init__.py": ""})
    write(tmp_path, {".gitignore": "__pycache__/\n.pytest_cache/\n/*.json\n"})

    class Tree:
        root = tmp_path
        path = proj

        def write(self, files):
            write(proj, files)

        def index(self):
            return Index(load(proj, root=tmp_path))

        def git(self, *args):
            return subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True,
                                  text=True).stdout

        def estoppel(self, *args):
            env = {"PYTHONPATH": str(M1), "PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
                   "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
                   "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
            return subprocess.run([sys.executable, "-m", "estoppel", *args], cwd=proj, env=env,
                                  capture_output=True, text=True)

    return Tree()
