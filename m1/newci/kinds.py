"""Checks that a change is the kind it is declared to be.

- publish:  adds definitions and changes none, checks included. Behaviour and claims are unchanged.
- activate: changes only bindings (and imports in binding modules). Checks may change with them.
- modify:   anything else.
None of the three may change the environment files, except modify.
"""

import os

from pydantic import BaseModel

from newci.defs import Diff, Index, diff

KINDS = ("publish", "activate", "modify")


class Verdict(BaseModel):
    declared: str
    ok: bool
    problems: list[str]
    bindings: list[str]              # binding definitions the change touched
    code: list[str]                  # other code definitions it changed or removed
    checks: list[str]                # check definitions it changed or removed
    added: int
    smallest: str                    # the narrowest kind the change qualifies as
    base: str = ""                   # the project's directory, for short names


def short(did: str, base: str = "") -> str:
    """A definition id with its file relative to `base`, the project's directory."""
    file, _, name = did.partition("::")
    return f"{os.path.relpath(file, base or '.')}::{name}"


def check(declared: str, before: Index, after: Index, env_changed: list[str]) -> Verdict:
    if declared not in KINDS:
        return Verdict(declared=declared, ok=False, problems=[f"unknown kind {declared!r}"],
                       bindings=[], code=[], checks=[], added=0, smallest="modify")
    d: Diff = diff(before, after)
    edited = d.changed | d.removed
    bindings = sorted(x for x in d.touched if is_binding_change(before, after, x))
    code = sorted(x for x in edited if not before.is_test(x) and x not in bindings)
    checks = sorted(x for x in edited if before.is_test(x))
    existing = [x for x in bindings if x not in d.added]
    if not edited and not env_changed:
        smallest = "publish"
    elif not env_changed and not code and existing:
        smallest = "activate"
    else:
        smallest = "modify"
    base = after.project.arm_rel
    problems = []
    if declared == "publish":
        problems += [f"changes {short(x, base)}" for x in sorted(edited)]
        problems += [f"changes environment file {f}" for f in env_changed]
    elif declared == "activate":
        problems += [f"changes {short(x, base)}, which is not a binding" for x in code]
        problems += [f"changes environment file {f}" for f in env_changed]
        if not existing:
            problems.append("changes no existing binding")
    return Verdict(declared=declared, ok=not problems, problems=problems, bindings=bindings,
                   code=code, checks=checks, added=len(d.added), smallest=smallest, base=base)


def is_binding_change(before: Index, after: Index, did: str) -> bool:
    """A binding, or an import in a module that holds bindings."""
    if before.is_binding(did) or after.is_binding(did):
        return True
    d = after.defs.get(did) or before.defs[did]
    return d.kind == "import" and (binding_module(before, did) or binding_module(after, did))


def binding_module(index: Index, did: str) -> bool:
    file = did.split("::")[0]
    return any(b.split("::")[0] == file for b in index.bindings)


def describe(v: Verdict) -> str:
    head = f"{v.declared}: {'ok' if v.ok else 'NOT ' + v.declared}"
    parts = [f"{v.added} definitions added"]
    if v.bindings:
        parts.append("bindings " + ", ".join(short(b, v.base) for b in v.bindings))
    if v.code:
        parts.append(f"{len(v.code)} code definitions changed")
    if v.checks:
        parts.append(f"{len(v.checks)} checks changed")
    lines = [f"{head} ({'; '.join(parts)})"]
    lines += [f"    {p}" for p in v.problems]
    if not v.ok and v.declared in KINDS:
        lines.append(f"    declare it as {v.smallest}, or split it")
    if v.ok and v.smallest != v.declared and KINDS.index(v.smallest) < KINDS.index(v.declared):
        lines.append(f"    note: this change also qualifies as {v.smallest}")
    return "\n".join(lines)
