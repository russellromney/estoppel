"""The definitions of a Python source tree: their hashes, and the definitions they refer to.

A definition is one top-level statement of a module: a function, a class, an assignment, or one
imported name. Its hash is of its syntax tree with docstrings removed, so comments, docstrings
and formatting do not change it. Other top-level statements (if, try, bare expressions) are
grouped into one `<toplevel>` definition per module.

A definition's id is `<file>::<name>`, with the file relative to the repository root, so ids are
the same in every worktree.
"""

import ast
import bisect
import hashlib
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from estoppel.config import Project

Kind = Literal["function", "class", "value", "import", "toplevel"]
TOPLEVEL = "<toplevel>"


class Definition(BaseModel):
    id: str
    kind: Kind
    hash: str
    file: str
    spans: tuple[tuple[int, int], ...]
    names: tuple[str, ...]          # module-level names it binds
    harness: bool = False           # a pytest hook or autouse fixture in a conftest.py
    refs: tuple[str, ...] = ()      # ids of the definitions it refers to


class Import(BaseModel):
    """One imported name. `module` is absolute; for `import a.b`, `name` is None."""

    module: str
    name: str | None
    asname: str | None


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def strip_docstrings(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                node.body = body[1:] or ([] if isinstance(node, ast.Module) else [ast.Pass()])


def chains(node: ast.AST) -> set[tuple[str, ...]]:
    """Names a node refers to, with attribute access: `a.b.c` gives ("a", "b", "c") and ("a",)."""
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            out.add((n.id,))
        elif isinstance(n, ast.Attribute):
            parts, cur = [], n
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                out.add((cur.id, *reversed(parts)))
    return out


def target_names(target: ast.expr) -> list[str] | None:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        names = []
        for t in target.elts:
            inner = target_names(t.value if isinstance(t, ast.Starred) else t)
            if inner is None:
                return None
            names += inner
        return names
    return None


def is_autouse(node: ast.AST) -> bool:
    return any(isinstance(n, ast.keyword) and n.arg == "autouse" for d in node.decorator_list
               for n in ast.walk(d))


def span(node: ast.stmt) -> tuple[int, int]:
    first = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
    return first, node.end_lineno


class Module:
    def __init__(self, rel: str, path: Path, dotted: list[str] | None):
        self.rel = rel
        self.path = path
        self.dotted = dotted            # the module's dotted name, when it is importable
        self.defs: dict[str, Definition] = {}
        self.bound: dict[str, list[str]] = {}
        self.imports: dict[str, Import] = {}
        self.chains: dict[str, set[tuple[str, ...]]] = {}


class Index:
    """The definitions of the sources in a project, as files on disk."""

    def __init__(self, project: Project):
        self.project = project
        self.root = project.root
        cfg = project.config
        self.search = [(project.arm / p).resolve() for p in cfg.path]
        self.modules: dict[str, Module] = {}
        self.defs: dict[str, Definition] = {}
        self._spans: dict[str, tuple[list[int], list[tuple[int, int, str]]]] = {}
        self._by_path: dict[str, str | None] = {}
        for path in self.source_files():
            self._parse(path)
        for module in self.modules.values():
            self._resolve_refs(module)
        self.tests = tuple(project.rel(t) for t in cfg.tests)
        self.bindings = self._bindings()
        self.harness = digest("".join(sorted(d.hash for d in self.defs.values() if d.harness)))

    # Reading files

    def source_files(self) -> list[Path]:
        out = []
        for entry in self.project.config.sources:
            p = (self.project.arm / entry).resolve()
            if p.is_file():
                out.append(p)
            elif p.is_dir():
                out += sorted(q for q in p.rglob("*.py")
                              if "__pycache__" not in q.parts and not any(
                                  part.startswith(".") for part in q.relative_to(p).parts))
        return out

    def _module_name(self, path: Path) -> list[str] | None:
        for base in self.search:
            if path.is_relative_to(base):
                parts = list(path.relative_to(base).with_suffix("").parts)
                return parts[:-1] if parts[-1] == "__init__" else parts
        return None

    def _parse(self, path: Path) -> None:
        rel = path.relative_to(self.root).as_posix()
        module = Module(rel, path, self._module_name(path))
        self.modules[rel] = module
        tree = ast.parse(path.read_text(), str(path))
        strip_docstrings(tree)
        toplevel: list[ast.stmt] = []
        toplevel_spans: list[tuple[int, int]] = []
        conftest = path.name == "conftest.py"
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class" if isinstance(node, ast.ClassDef) else "function"
                harness = conftest and (node.name.startswith("pytest_") or (
                    kind == "function" and is_autouse(node)))
                self._add(module, kind, [node.name], node, [span(node)], harness=harness)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                names = [n for t in targets for n in (target_names(t) or [None])]
                if None in names:
                    toplevel.append(node)
                    toplevel_spans.append(span(node))
                    continue
                harness = conftest and any(n.startswith("pytest_") for n in names)
                self._add(module, "value", names, node, [span(node)], harness=harness)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    self._add_import(module, node, alias)
            else:
                toplevel.append(node)
                toplevel_spans.append(span(node))
        if toplevel:
            names = sorted({n.id for stmt in toplevel for n in ast.walk(stmt)
                            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)})
            block = ast.Module(body=toplevel, type_ignores=[])
            self._add(module, "toplevel", names, block, toplevel_spans, name=TOPLEVEL)

    def _add(self, module: Module, kind: Kind, names: list[str], node: ast.AST,
             spans: list[tuple[int, int]], harness: bool = False, name: str | None = None,
             text: str | None = None) -> str:
        did = f"{module.rel}::{name or ','.join(names)}"
        n = 2
        while did in self.defs:
            did = f"{module.rel}::{name or ','.join(names)}#{n}"
            n += 1
        text = text if text is not None else ast.dump(node, include_attributes=False)
        d = Definition(id=did, kind=kind, hash=digest(f"{kind}\n{text}"), file=module.rel,
                       spans=tuple(spans), names=tuple(names), harness=harness)
        self.defs[did] = module.defs[did] = d
        for bound in names:
            module.bound.setdefault(bound, []).append(did)
        if kind != "import":
            module.chains[did] = chains(node)
        return did

    def _add_import(self, module: Module, node: ast.Import | ast.ImportFrom, alias: ast.alias):
        if isinstance(node, ast.Import):
            imp = Import(module=alias.name, name=None, asname=alias.asname)
            bound = alias.asname or alias.name.split(".")[0]
            label = f"import {alias.name}" + (f" as {alias.asname}" if alias.asname else "")
        else:
            base = node.module or ""
            if node.level:
                package = module.dotted or []
                if module.path.name != "__init__.py":
                    package = package[:-1]
                package = package[:len(package) - (node.level - 1)]
                base = ".".join([*package, *([node.module] if node.module else [])])
            imp = Import(module=base, name=alias.name, asname=alias.asname)
            bound = alias.asname or alias.name
            label = f"from {base} import {alias.name}" + (f" as {alias.asname}" if alias.asname else "")
        did = self._add(module, "import", [bound], node, [span(node)], name=label,
                        text=imp.model_dump_json())
        module.imports[did] = imp

    # Resolving names

    def module_file(self, dotted: str) -> str | None:
        parts = dotted.split(".") if dotted else []
        for base in self.search:
            for candidate in (base.joinpath(*parts).with_suffix(".py") if parts else None,
                              base.joinpath(*parts, "__init__.py")):
                if candidate is not None and candidate.is_file():
                    try:
                        rel = candidate.relative_to(self.root).as_posix()
                    except ValueError:
                        return None
                    return rel if rel in self.modules else None
        return None

    def _submodule(self, rel: str, name: str) -> str | None:
        module = self.modules[rel]
        if module.path.name != "__init__.py" or module.dotted is None:
            return None
        return self.module_file(".".join([*module.dotted, name]))

    def resolve(self, rel: str, chain: tuple[str, ...], depth: int = 0) -> list[str]:
        """The definitions that `chain`, looked up in module `rel`, refers to."""
        if depth > 30 or not chain:
            return []
        module = self.modules[rel]
        ids = module.bound.get(chain[0], [])
        if not ids:
            sub = self._submodule(rel, chain[0])
            return self._module_attr(sub, chain[1:], depth + 1) if sub else []
        out = []
        for did in ids:
            out.append(did)
            if did in module.imports:
                out += self._follow(module.imports[did], chain[1:], depth + 1)
        return out

    def _follow(self, imp: Import, rest: tuple[str, ...], depth: int) -> list[str]:
        if imp.name is None:
            dotted = imp.module if imp.asname else imp.module.split(".")[0]
            target = self.module_file(dotted)
            return self._module_attr(target, rest, depth) if target else []
        target = self.module_file(imp.module)
        if target is None:
            return []
        if imp.name not in self.modules[target].bound:
            sub = self.module_file(f"{imp.module}.{imp.name}" if imp.module else imp.name)
            if sub:
                return self._module_attr(sub, rest, depth)
        return self.resolve(target, (imp.name, *rest), depth)

    def _module_attr(self, rel: str, rest: tuple[str, ...], depth: int) -> list[str]:
        if not rest:
            return []
        return self.resolve(rel, rest, depth)

    def _resolve_refs(self, module: Module) -> None:
        for did, d in module.defs.items():
            if did in module.imports:
                refs = self._follow(module.imports[did], (), 0)
            else:
                refs = [r for chain in module.chains[did] for r in self.resolve(module.rel, chain)]
                refs += [t for t in module.defs if t.endswith(f"::{TOPLEVEL}")]
            refs = tuple(sorted(set(refs) - {did}))
            self.defs[did] = module.defs[did] = d.model_copy(update={"refs": refs})

    def _bindings(self) -> frozenset[str]:
        out = set()
        for file, names in self.project.config.bindings.items():
            module = self.modules.get(self.project.rel(file))
            if module is None:
                continue
            for did, d in module.defs.items():
                if "*" in names or set(d.names) & set(names):
                    out.add(did)
        return frozenset(out)

    # Questions about definitions

    def is_test(self, did: str) -> bool:
        file = did.split("::")[0]
        return any(file == t or file.startswith(t + "/") for t in self.tests)

    def is_binding(self, did: str) -> bool:
        return did in self.bindings

    def at(self, filename: str, line: int, name: str = "") -> list[str]:
        """The definitions that a code object starting at `line` of `filename` belongs to."""
        rel = self._by_path.get(filename, "")
        if rel == "":
            real = os.path.realpath(filename)
            root = str(self.root) + os.sep
            rel = real[len(root):].replace(os.sep, "/") if real.startswith(root) else None
            rel = rel if rel in self.modules else None
            self._by_path[filename] = rel
        if rel is None:
            return []
        module = self.modules[rel]
        if name == "<module>":
            return [did for did, d in module.defs.items() if d.kind != "function"]
        if rel not in self._spans:
            spans = sorted((s, e, did) for did, d in module.defs.items() for s, e in d.spans)
            self._spans[rel] = ([s for s, _, _ in spans], spans)
        starts, spans = self._spans[rel]
        i = bisect.bisect_right(starts, line) - 1
        if i >= 0 and spans[i][0] <= line <= spans[i][1]:
            return [spans[i][2]]
        return []

    def closure(self, seeds: Iterable[str]) -> set[str]:
        """`seeds` and every definition they refer to, transitively, except functions.

        A function that did not run cannot have affected a check. Everything else that is
        referred to (values, classes, imports, module-level statements) may have, without
        running any code of its own.
        """
        out = set(seeds)
        stack = list(out)
        while stack:
            for ref in self.defs[stack.pop()].refs:
                if ref not in out and self.defs[ref].kind != "function":
                    out.add(ref)
                    stack.append(ref)
        return out

    def hashes(self) -> dict[str, str]:
        return {did: d.hash for did, d in self.defs.items()}


class Diff(BaseModel):
    added: frozenset[str]
    removed: frozenset[str]
    changed: frozenset[str]

    @property
    def touched(self) -> frozenset[str]:
        return self.added | self.removed | self.changed


def diff(before: Index, after: Index) -> Diff:
    a, b = before.hashes(), after.hashes()
    return Diff(added=frozenset(b.keys() - a.keys()), removed=frozenset(a.keys() - b.keys()),
                changed=frozenset(k for k in a.keys() & b.keys() if a[k] != b[k]))
