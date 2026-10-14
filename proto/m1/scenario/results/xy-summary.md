| # | Step | Role | Command | Exit | Ran | By tier | Kept | Share | Check s | Pytest | CPU s | Wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | base-a | measure | `uv run pytest --testmon -q` | 0 | 374 | t1 30, t2 36, t3 301, t4 7 |  | 98.4% (3 unmatched) | 13.65 | 374 passed | 12.4 | 15.38 |
| 2 | base-b | measure | `uv run pytest --testmon -q` | 0 | 435 | t1 85, t2 40, t3 302, t4 8 |  | 100.0% | 18.16 | 435 passed | 17.49 | 19.63 |
| 3 | a-x | agent | `uv run pytest --testmon -q` | 0 | 323 | t1 11, t2 3, t3 301, t4 8 |  | 100.0% | 10.41 | 323 passed, 2 deselected | 11.33 | 11.53 |
| 4 | a-x | agent | `git add -A && git commit -q -m "b2g1: every third unit of a SKU is free"` | 0 |  |  |  |  |  |  | 0.07 | 0.08 |
| 5 | a-y | agent | `uv run pytest --testmon -q` | 0 | 342 | t1 14, t2 18, t3 301, t4 9 |  | 93.5% | 9.73 | 342 passed, 13 deselected | 10.66 | 10.71 |
| 6 | a-y | agent | `git add -A && git commit -q -m "category_windows: refund windows by product category"` | 0 |  |  |  |  |  |  | 0.06 | 0.08 |
| 7 | a-combine | integrator | `git merge -q --no-edit scn/a-x scn/a-y` | 0 |  |  |  |  |  |  | 0.27 | 0.3 |
| 8 | a-combine | integrator | `uv run pytest --testmon -q  (testmon data: base)` | 0 | 357 | t1 25, t2 21, t3 301, t4 10 |  | 100.0% | 10.33 | 357 passed, 15 deselected | 11.3 | 11.36 |
| 9 | a-combine | measure | `uv run pytest --testmon -q  (testmon data: x)` | 0 | 343 | t1 14, t2 18, t3 301, t4 10 |  | 93.5% | 9.66 | 343 passed, 13 deselected | 10.59 | 10.64 |
| 10 | a-combine | audit | `uv run pytest -q -p no:cacheprovider` | 0 |  |  |  |  | 4.23 | 387 passed | 4.55 | 4.94 |
| 11 | a-probe-config | probe | `uv run pytest --testmon -q  (testmon data: int)` | 0 | 0 |  |  |  | 0 |  | 0.45 | 0.48 |
| 12 | a-probe-config | probe | `uv run pytest -q -p no:cacheprovider --tb=line` | 1 |  |  |  |  |  | 226 failed, 161 passed | 2.56 | 2.58 |
| 13 | a-combine | audit | `uv run pytest acceptance --arm a --features b2g1,category_windows -q -p no:cacheprovider` | 0 |  |  |  |  |  | 107 passed | 0.78 | 0.79 |
| 14 | b-x-publish | agent | `uv run python ../newci gate --kind publish` | 0 | 9 | t1 9 | 435 | 0.0% | 0.01 | 9 passed, 435 deselected, 0 failed | 1.1 | 1.13 |
| 15 | b-x-publish | measure | `uv run pytest --testmon -q` | 0 | 9 | t1 9 |  | 0.0% | 0.0 | 9 passed | 0.5 | 0.52 |
| 16 | b-x-publish | agent | `git add -A && git commit -q -m "b2g1: publish the rule" -m "Newci-Kind: publish"` | 0 |  |  |  |  |  |  | 0.07 | 0.08 |
| 17 | b-x-activate | agent | `uv run python ../newci gate --kind activate` | 0 | 31 | t1 22, t4 9 | 414 | 0.5% | 0.05 | 31 passed, 414 deselected, 0 failed | 1.18 | 1.2 |
| 18 | b-x-activate | measure | `uv run pytest --testmon -q` | 0 | 1 | t4 1 |  | 0.0% | 0.0 | 1 passed | 0.51 | 0.53 |
| 19 | b-x-activate | agent | `git add -A && git commit -q -m "b2g1: activate the rule" -m "Newci-Kind: activate"` | 0 |  |  |  |  |  |  | 0.05 | 0.06 |
| 20 | b-y-publish | agent | `uv run python ../newci gate --kind publish` | 0 | 6 | t1 6 | 435 | 0.0% | 0.01 | 6 passed, 435 deselected, 0 failed | 1.08 | 1.1 |
| 21 | b-y-publish | measure | `uv run pytest --testmon -q` | 0 | 25 | t1 17, t4 8 |  | 0.0% | 0.01 | 25 passed, 14 deselected | 0.58 | 0.6 |
| 22 | b-y-publish | agent | `git add -A && git commit -q -m "category_windows: publish windows by category" -m "Newci-Kind: publish"` | 0 |  |  |  |  |  |  | 0.07 | 0.08 |
| 23 | b-y-modify | agent | `uv run python ../newci gate --kind modify` | 0 | 10 | t1 5, t4 5 | 433 | 0.0% | 0.01 | 10 passed, 433 deselected, 0 failed | 1.12 | 1.15 |
| 24 | b-y-modify | probe | `uv run python ../newci gate --kind activate` | 2 |  |  |  |  |  |  | 0.45 | 0.46 |
| 25 | b-y-modify | measure | `uv run pytest --testmon -q` | 0 | 27 | t1 17, t4 10 |  | 0.0% | 0.02 | 27 passed, 14 deselected | 0.58 | 0.59 |
| 26 | b-y-modify | agent | `git add -A && git commit -q -m "category_windows: use them in the refund policy" -m "Newci-Kind: modify"` | 0 |  |  |  |  |  |  | 0.05 | 0.06 |
| 27 | b-combine | integrator | `uv run python ../newci combine scn/b-x scn/b-y` | 0 | 6 | t4 6 | 447 | 0.0% | 0.01 | 6 passed, 447 deselected, 0 failed | 2.97 | 3.11 |
| 28 | b-combine | measure | `uv run pytest --testmon -q  (testmon data: base)` | 0 | 37 | t1 26, t4 11 |  | 0.0% | 0.02 | 37 passed, 14 deselected | 0.62 | 0.64 |
| 29 | b-combine | measure | `uv run pytest --testmon -q  (testmon data: x)` | 0 | 28 | t1 17, t4 11 |  | 0.0% | 0.02 | 28 passed, 14 deselected | 0.6 | 0.62 |
| 30 | b-combine | audit | `uv run pytest -q -p no:cacheprovider` | 0 |  |  |  |  | 5.6 | 453 passed | 6.25 | 6.27 |
| 31 | b-probe-config | probe | `uv run pytest --testmon -q  (testmon data: int)` | 0 | 0 |  |  |  | 0 |  | 0.43 | 0.44 |
| 32 | b-probe-config | probe | `uv run python ../newci gate` | 1 |  |  |  |  |  | 9 failed, 11 passed, 433 deselected | 0.9 | 0.92 |
| 33 | b-probe-config | probe | `uv run pytest -q -p no:cacheprovider --tb=line` | 1 |  |  |  |  |  | 9 failed, 444 passed | 6.25 | 6.34 |
| 34 | b-probe-binding | probe | `uv run pytest --testmon -q  (testmon data: int)` | 0 | 0 |  |  |  | 0 |  | 0.45 | 0.47 |
| 35 | b-probe-binding | probe | `uv run python ../newci gate` | 1 |  |  |  |  |  | 1 failed, 452 deselected | 0.92 | 1.04 |
| 36 | b-probe-binding | probe | `uv run pytest -q -p no:cacheprovider --tb=line` | 1 |  |  |  |  |  | 1 failed, 452 passed | 6.31 | 6.35 |
| 37 | b-combine | audit | `uv run pytest acceptance --arm b --features b2g1,category_windows -q -p no:cacheprovider` | 0 |  |  |  |  |  | 107 passed | 1.28 | 1.29 |

| Branch | Lines changed by area |
|---|---|
| scn/a-x | rules and policies 7, tests 33 |
| scn/a-y | rules and policies 14, tests 52 |
| scn/a-int | rules and policies 21, tests 85 |
| scn/b-x | claims (files) 29, periphery 15, tests 52 |
| scn/b-y | claims (files) 13, periphery 14, tests 47 |
| scn/b-int | claims (files) 49, periphery 29, tests 99 |
