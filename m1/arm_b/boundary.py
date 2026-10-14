"""The boundary lint. The gate runs it on every change:  uv run python boundary.py

Periphery code (everything in checkout/ outside checkout/core/) may not:
  - import core modules other than checkout.core.api, or the world (clock, provider);
  - read the clock or randomness, or do I/O;
  - use reflection (getattr, setattr, eval, ...);
  - keep mutable state at module or class level, or use `global`;
  - reach into other objects' private attributes.
Core code may not import the periphery.
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT / "checkout"
CORE = PACKAGE / "core"

FORBIDDEN_MODULES = {
    "world", "time", "datetime", "random", "secrets", "os", "sys", "io", "socket", "pathlib",
    "subprocess", "threading", "multiprocessing", "asyncio", "uuid", "urllib", "http", "shutil",
    "tempfile", "sqlite3", "logging", "importlib", "builtins", "inspect", "gc", "ctypes", "pickle",
}
FORBIDDEN_CALLS = {
    "open", "print", "input", "exec", "eval", "compile", "__import__", "globals", "locals", "vars",
    "getattr", "setattr", "delattr",
}
MUTABLE_CALLS = {"list", "dict", "set", "bytearray", "defaultdict", "deque", "Counter", "OrderedDict"}
MUTABLE_DISPLAYS = (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)


def imported_modules(node) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.module:
        if node.module == "checkout.core":
            return [f"checkout.core.{alias.name}" for alias in node.names]
        return [node.module]
    return []


def mutable(value) -> bool:
    if isinstance(value, MUTABLE_DISPLAYS):
        return True
    if isinstance(value, ast.Call):
        name = value.func.id if isinstance(value.func, ast.Name) else getattr(value.func, "attr", "")
        return name in MUTABLE_CALLS
    if isinstance(value, ast.Tuple):
        return any(mutable(element) for element in value.elts)
    return False


def check_periphery(tree: ast.Module) -> list[tuple[int, str]]:
    problems = []
    for node in ast.walk(tree):
        for module in imported_modules(node):
            top = module.split(".")[0]
            if module.startswith("checkout.core") and module != "checkout.core.api":
                problems.append((node.lineno, f"imports {module}; use checkout.core.api"))
            elif top in FORBIDDEN_MODULES:
                problems.append((node.lineno, f"imports {module}"))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in FORBIDDEN_CALLS:
            problems.append((node.lineno, f"calls {node.func.id}"))
        if isinstance(node, ast.Global):
            problems.append((node.lineno, "uses global"))
        if isinstance(node, ast.Attribute) and node.attr.startswith("_") \
                and not node.attr.startswith("__") \
                and not (isinstance(node.value, ast.Name) and node.value.id in ("self", "cls")):
            problems.append((node.lineno, f"reads private attribute {node.attr}"))
    scopes = [tree.body] + [n.body for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    for body in scopes:
        for stmt in body:
            value = stmt.value if isinstance(stmt, (ast.Assign, ast.AnnAssign)) else None
            if value is not None and mutable(value):
                problems.append((stmt.lineno, "mutable state at module or class level"))
    return problems


def check_core(tree: ast.Module) -> list[tuple[int, str]]:
    return [(node.lineno, f"core imports the periphery ({module})")
            for node in ast.walk(tree) for module in imported_modules(node)
            if module == "checkout" or module.startswith("checkout.app")]


def check_file(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), str(path))
    in_core = CORE in path.parents
    found = check_core(tree) if in_core else check_periphery(tree)
    return [f"{path.relative_to(ROOT)}:{line}: {message}" for line, message in found]


def main() -> int:
    problems = [p for path in sorted(PACKAGE.rglob("*.py")) for p in check_file(path)]
    for problem in problems:
        print(problem)
    print(f"boundary: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
