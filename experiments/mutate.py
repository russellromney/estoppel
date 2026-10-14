"""First-order mutants of a restricted planner (operators M1-M8, E1b).

Each mutant applies one operator at one site. Sites are found by walking
a fresh copy of the syntax tree in `ast.walk` order, so mutant ids are
stable for a given source.
"""

import ast
import copy
from dataclasses import dataclass

CMP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
       ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.In: ast.NotIn, ast.NotIn: ast.In,
       ast.Is: ast.IsNot, ast.IsNot: ast.Is}
ARITH = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Add}
BOOL = {ast.And: ast.Or, ast.Or: ast.And}


@dataclass(frozen=True)
class Mutant:
    id: str
    op: str
    line: int
    change: str
    source: str


def _docstrings(tree) -> set[int]:
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                out.add(id(first.value))
    return out


def _is_guard(node) -> bool:
    return (isinstance(node, ast.If) and not node.orelse
            and len(node.body) == 1 and isinstance(node.body[0], ast.Return))


def _replace(parents, node, new):
    """Replace `node` in its parent with `new` (None deletes a statement)."""
    parent = parents[id(node)]
    for field, value in ast.iter_fields(parent):
        if isinstance(value, list) and any(v is node for v in value):
            i = next(i for i, v in enumerate(value) if v is node)
            if new is None:
                del value[i]
                if not value:
                    value.append(ast.Pass())
            else:
                value[i] = new
            return
        if value is node:
            setattr(parent, field, new)
            return
    raise AssertionError("node not found in parent")


def _edits(node, docstrings):
    """Yield (op, change, apply) for each mutation that fits `node`.

    `apply(node, parents)` mutates the tree that contains `node`.
    """
    if isinstance(node, ast.Compare):
        for i, cmp in enumerate(node.ops):
            new = CMP.get(type(cmp))
            if new:
                def apply(n, p, i=i, new=new):
                    n.ops[i] = new()
                yield "M1", f"{type(cmp).__name__}->{new.__name__}", apply
    if isinstance(node, ast.BinOp) and type(node.op) in ARITH:
        new = ARITH[type(node.op)]

        def apply(n, p, new=new):
            n.op = new()
        yield "M2", f"{type(node.op).__name__}->{new.__name__}", apply
    if isinstance(node, ast.Constant) and type(node.value) is int:
        n0 = node.value

        def plus(n, p):
            n.value = n0 + 1
        yield "M3", f"{n0}->{n0 + 1}", plus
        if n0 != 0:
            def zero(n, p):
                n.value = 0
            yield "M3", f"{n0}->0", zero
    if isinstance(node, ast.Constant) and type(node.value) is str and id(node) not in docstrings:
        def apply(n, p):
            n.value = n.value + "_x"
        yield "M4", f"{node.value!r}->{node.value + '_x'!r}", apply
    if isinstance(node, ast.BoolOp):
        new = BOOL[type(node.op)]

        def apply(n, p, new=new):
            n.op = new()
        yield "M5", f"{type(node.op).__name__}->{new.__name__}", apply
    if isinstance(node, ast.If):
        def negate(n, p):
            n.test = ast.UnaryOp(op=ast.Not(), operand=n.test)
        yield "M6", f"negate `if {ast.unparse(node.test)}`", negate
    if _is_guard(node):
        def delete(n, p):
            _replace(p, n, None)
        yield "M7", f"delete guard `if {ast.unparse(node.test)}`", delete
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        def drop(n, p):
            _replace(p, n, n.operand)
        yield "M8", f"drop not in `{ast.unparse(node)}`", drop


def mutants(name: str, source: str) -> list[Mutant]:
    tree = ast.parse(source)
    original = ast.unparse(tree)
    sites = []
    for idx, node in enumerate(ast.walk(tree)):
        for k, (op, change, _) in enumerate(_edits(node, _docstrings(tree))):
            sites.append((idx, k, op, change, getattr(node, "lineno", 0)))
    out, seen = [], set()
    for idx, k, op, change, line in sites:
        t = copy.deepcopy(tree)
        nodes = list(ast.walk(t))
        parents = {id(c): p for p in nodes for c in ast.iter_child_nodes(p)}
        node = nodes[idx]
        _, _, apply = list(_edits(node, _docstrings(t)))[k]
        apply(node, parents)
        src = ast.unparse(ast.fix_missing_locations(t))
        if src == original or src in seen:
            continue
        seen.add(src)
        out.append(Mutant(f"{name}~{op}@{line}.{idx}.{k}", op, line, change, src))
    return out
