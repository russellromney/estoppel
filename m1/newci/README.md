# newci: the minimal change workflow

This is the change workflow from the plan's section 3.2. It is a script over ordinary Python files, with git underneath. Arm B uses it. [`../arm_b/AGENTS.md`](../arm_b/AGENTS.md) is the agent-facing guide.

| Part | Where | What it does |
|---|---|---|
| Definitions | `defs.py` | Every top-level statement of every source file, hashed by its syntax tree. Comments, docstrings and layout do not change a hash. Each definition also lists the definitions it refers to, through imports and re-exports. |
| Bindings | `newci.toml` | The definitions where a consumer selects an implementation. For arm B: `RULES`, `composition.py` and `config.py`. |
| Kinds | `kinds.py` | `publish` only adds definitions. `activate` changes only bindings. `modify` is anything else. The gate checks the working tree against a declared kind, and `combine` checks every commit's `Newci-Kind:` trailer. |
| Claims | `claims.py`, `plugin.py` | A pytest plugin records each check's footprint and writes a claim for each check that passes. A check with a valid claim is skipped. |
| Commands | `cli.py` | `gate`, `kinds` and `combine` |

## Footprints

A check's footprint is recorded at definition granularity while the check runs. It contains:
- every definition whose code started running, seen through `sys.monitoring`;
- the definitions of the fixtures the check requested, since a fixture may have run before the check;
- everything those definitions refer to, transitively, except functions that did not run. Values, classes and imports can change behaviour without running code of their own;
- files under the repository root that the check opened;
- the harness: pytest hooks and autouse fixtures in `conftest.py` files.

A claim is valid when every hash in its footprint matches the current tree, and its environment matches. The environment is the Python version, the pytest version, the checker's own source, and the files listed under `env` in `newci.toml` (for arm B, these include `uv.lock` and `pytest.ini`).

## The claim store

The store is the `.newci/` directory, committed with the code:
- `footprints/<key>.json` holds one footprint, shared by every claim that has it;
- `claims/<key>.jsonl` holds the claims written by one run.

Every file is named by a hash of its content. Two branches never write the same file differently, so git merges stores without conflicts. A full run of arm B writes 87 footprints, about 0.9 MB.

## Known gaps

A footprint can miss a dependency in these cases. The audit (the arm's full suite, plus the acceptance suite) is the backstop for all of them.

- **Dynamic lookup.** A name reached only through `getattr`, `globals()` or `importlib` is not followed. The boundary lint bans these in arm B's periphery, but not in its core or tests.
- **Import-time effects of new modules.** A published module that registers itself when imported would change behaviour without changing any existing definition. In arm B's periphery, the lint's ban on mutable module state prevents this.
- **String annotations.** Names inside annotations written as strings are not followed.
- **Code outside the sources.** Third-party packages and the standard library are covered only through `uv.lock` and the Python version.
- **Order between checks.** A check that depends on state left behind by an earlier check in the same process is not tracked.

It is also coarse in one place. A class is one definition, so changing any method reruns every check that used the class.

## Tests

```bash
uv run pytest newci/tests      # from m1/
```
