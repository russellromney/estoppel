"""Loader for planners written in a restricted subset of Python.

The subset makes planners pure and terminating by construction:
no imports, no globals, no while loops, no recursion (a function may
call only functions defined above it), no try/except, no names that
start with an underscore, and only whitelisted builtins and methods.
Snapshots passed to planners are frozen (see `freeze`).

This is enforcement for a cooperative experiment, not a security
sandbox. It establishes that a planner in this subset cannot reach
ambient I/O, time, randomness or mutable shared state.
"""

import ast
import builtins
import hashlib
from dataclasses import dataclass
from types import MappingProxyType

MAX_RANGE = 10_000


def _bounded_range(*args):
    r = range(*args)
    if len(r) > MAX_RANGE:
        raise ValueError(f"range longer than {MAX_RANGE}")
    return r


ALLOWED_BUILTINS = {
    name: getattr(builtins, name)
    for name in (
        "abs", "all", "any", "bool", "dict", "enumerate", "int", "len", "list",
        "max", "min", "round", "set", "sorted", "str", "sum", "tuple", "zip",
    )
}
ALLOWED_BUILTINS["range"] = _bounded_range
ALLOWED_BUILTINS["True"] = True
ALLOWED_BUILTINS["False"] = False
ALLOWED_BUILTINS["None"] = None

ALLOWED_METHODS = {
    "append", "count", "endswith", "extend", "get", "index", "items", "join",
    "keys", "lower", "setdefault", "split", "startswith", "strip", "update",
    "upper", "values",
}

ALLOWED_NODES = (
    ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return, ast.Assign,
    ast.AugAssign, ast.AnnAssign, ast.For, ast.If, ast.IfExp, ast.Compare,
    ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.Call, ast.keyword, ast.Name,
    ast.Constant, ast.Tuple, ast.List, ast.Dict, ast.Set, ast.ListComp,
    ast.DictComp, ast.SetComp, ast.GeneratorExp, ast.comprehension,
    ast.Subscript, ast.Slice, ast.Attribute, ast.Expr, ast.Pass, ast.Break,
    ast.Continue, ast.JoinedStr, ast.FormattedValue, ast.Starred,
    ast.Load, ast.Store, ast.expr_context, ast.operator, ast.boolop,
    ast.cmpop, ast.unaryop,
)


class RestrictionError(Exception):
    pass


def _fail(node, msg):
    line = getattr(node, "lineno", "?")
    raise RestrictionError(f"line {line}: {msg}")


def _bound_names(fn: ast.FunctionDef) -> set[str]:
    names = {a.arg for a in fn.args.args}
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
    return names


def validate(source: str) -> ast.Module:
    """Check that `source` is in the restricted subset. Return its AST."""
    tree = ast.parse(source)
    constants: set[str] = set()
    functions: list[str] = []

    for stmt in tree.body:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            continue  # docstring
        if isinstance(stmt, ast.Assign):
            if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
                _fail(stmt, "module-level assignment must bind one name")
            name = stmt.targets[0].id
            if not name.isupper():
                _fail(stmt, f"module-level name {name!r} must be an UPPER_CASE constant")
            try:
                ast.literal_eval(stmt.value)
            except ValueError:
                _fail(stmt, f"constant {name!r} must be a literal")
            constants.add(name)
            continue
        if isinstance(stmt, ast.FunctionDef):
            if stmt.decorator_list:
                _fail(stmt, "decorators are not allowed")
            if stmt.args.vararg or stmt.args.kwarg or stmt.args.kwonlyargs or stmt.args.defaults:
                _fail(stmt, "only plain positional parameters are allowed")
            _validate_function(stmt, constants, set(functions))
            functions.append(stmt.name)
            continue
        _fail(stmt, f"{type(stmt).__name__} is not allowed at module level")

    if "propose" not in functions:
        raise RestrictionError("planner must define propose(request, snapshot)")
    return tree


def _validate_function(fn: ast.FunctionDef, constants: set[str], earlier: set[str]):
    local = _bound_names(fn)
    visible = local | constants | earlier | set(ALLOWED_BUILTINS)
    for node in ast.walk(fn):
        if node is fn:
            continue
        if isinstance(node, ast.FunctionDef):
            _fail(node, "nested functions are not allowed")
        if not isinstance(node, ALLOWED_NODES):
            _fail(node, f"{type(node).__name__} is not allowed")
        if isinstance(node, ast.Name):
            if node.id.startswith("_"):
                _fail(node, f"name {node.id!r} starts with an underscore")
            if isinstance(node.ctx, ast.Load) and node.id not in visible:
                _fail(node, f"name {node.id!r} is not defined in the planner")
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("_"):
                _fail(node, f"attribute {node.attr!r} starts with an underscore")
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                if func.id == fn.name:
                    _fail(node, "recursion is not allowed")
                if func.id not in ALLOWED_BUILTINS and func.id not in earlier:
                    _fail(node, f"call to {func.id!r} is not allowed")
            elif isinstance(func, ast.Attribute):
                if func.attr not in ALLOWED_METHODS:
                    _fail(node, f"method {func.attr!r} is not allowed")
            else:
                _fail(node, "only direct calls are allowed")
    # Attributes may only appear as method calls.
    for node in ast.walk(fn):
        if isinstance(node, ast.Attribute):
            parent_ok = any(
                isinstance(p, ast.Call) and p.func is node for p in ast.walk(fn)
            )
            if not parent_ok:
                _fail(node, f"attribute access {node.attr!r} is only allowed as a method call")


@dataclass(frozen=True)
class Planner:
    name: str
    source_hash: str
    propose: object


def load(name: str, source: str) -> Planner:
    validate(source)
    env = {"__builtins__": dict(ALLOWED_BUILTINS)}
    exec(compile(source, f"<planner {name}>", "exec"), env)
    digest = hashlib.sha256(source.encode()).hexdigest()[:16]
    return Planner(name=name, source_hash=digest, propose=env["propose"])


def freeze(value):
    """Deep-freeze a snapshot so planners cannot mutate kernel data."""
    if isinstance(value, dict):
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(v) for v in value)
    if isinstance(value, set):
        return frozenset(freeze(v) for v in value)
    return value


def thaw(value):
    """Convert planner output to plain dicts, tuples and scalars."""
    if isinstance(value, (dict, MappingProxyType)):
        return {k: thaw(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(thaw(v) for v in value)
    return value
