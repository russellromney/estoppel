"""estoppel: a minimal change workflow over ordinary Python files, with git underneath.

- `defs`: every top-level definition, hashed by its syntax tree, with the names it refers to.
- `claims`: claims that a check passed, keyed by the hashes of the definitions it used.
- `plugin`: a pytest plugin that skips checks with a valid claim and records claims for the rest.
- `kinds`: checks that a change is the `publish`, `activate` or `modify` it says it is.
- `cli`: `gate`, `kinds` and `combine`.
"""
