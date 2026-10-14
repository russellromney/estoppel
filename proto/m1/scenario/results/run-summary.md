| # | Step | Role | Command | Exit | Ran | By tier | Kept | Share | Check s | Pytest | CPU s | Wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | base-a | measure | `uv run pytest --testmon -q` | 0 | 374 | t1 30, t2 36, t3 301, t4 7 |  | 98.3% (3 unmatched) | 10.58 | 374 passed | 11.6 | 11.78 |
| 2 | base-b | measure | `uv run pytest --testmon -q` | 0 | 435 | t1 85, t2 40, t3 302, t4 8 |  | 100.0% | 15.26 | 435 passed | 16.39 | 16.59 |
| 3 | a-x | agent | `uv run pytest --testmon -q` | 0 | 323 | t1 11, t2 3, t3 301, t4 8 |  | 100.0% | 10.46 | 323 passed, 2 deselected | 11.39 | 11.51 |
| 4 | a-x | agent | `git add -A && git commit -q -m "b2g1: every third unit of a SKU is free"` | 0 |  |  |  |  |  |  | 0.09 | 0.11 |
| 5 | a-y | agent | `uv run pytest --testmon -q` | 0 | 342 | t1 14, t2 18, t3 301, t4 9 |  | 92.9% | 9.82 | 342 passed, 13 deselected | 10.77 | 10.89 |
| 6 | a-y | agent | `git add -A && git commit -q -m "category_windows: refund windows by product category"` | 0 |  |  |  |  |  |  | 0.09 | 0.11 |
| 7 | a-xy-combine | integrator | `git merge -q --no-edit scn/a-x scn/a-y` | 0 |  |  |  |  |  |  | 0.33 | 0.37 |
| 8 | a-xy-combine | integrator | `uv run pytest --testmon -q  (testmon data: base)` | 0 | 357 | t1 25, t2 21, t3 301, t4 10 |  | 100.0% | 10.31 | 357 passed, 15 deselected | 11.33 | 11.46 |
| 9 | a-xy-combine | measure | `uv run pytest --testmon -q  (testmon data: x)` | 0 | 343 | t1 14, t2 18, t3 301, t4 10 |  | 92.9% | 9.84 | 343 passed, 13 deselected | 10.81 | 10.93 |
| 10 | a-xy-combine | audit | `uv run pytest -q -p no:cacheprovider` | 0 |  |  |  |  | 4.0 | 387 passed | 4.62 | 4.72 |
| 11 | a-xy-combine | audit | `uv run pytest acceptance --arm a --features b2g1,category_windows -q -p no:cacheprovider` | 0 |  |  |  |  |  | 107 passed | 0.82 | 0.83 |
| 12 | a-xy-probe-config | probe | `uv run pytest --testmon -q  (testmon data: int)` | 0 | 0 |  |  |  | 0 |  | 0.42 | 0.44 |
| 13 | a-xy-probe-config | probe | `uv run pytest -q -p no:cacheprovider --tb=line` | 1 |  |  |  |  |  | 226 failed, 161 passed | 2.61 | 2.63 |
| 14 | a-z | agent | `uv run pytest --testmon -q` | 0 | 388 | t1 37, t2 41, t3 301, t4 9 |  | 97.9% (3 unmatched) | 9.27 | 388 passed | 10.3 | 10.37 |
| 15 | a-z | agent | `git add -A && git commit -q -m "coupons: SAVE10, with a shared redemption limit"` | 0 |  |  |  |  |  |  | 0.09 | 0.11 |
| 16 | a-z-combine | integrator | `git merge -q --no-edit scn/a-z` | 1 |  |  |  |  |  |  | 0.04 | 0.05 |
| 17 | a-z-combine | integrator | `(copy the resolution's files)` | 0 |  |  |  |  |  |  | 0.01 | 0.01 |
| 18 | a-z-combine | integrator | `git add -A && git commit -q --no-edit` | 0 |  |  |  |  |  |  | 0.05 | 0.06 |
| 19 | a-z-combine | integrator | `uv run pytest --testmon -q  (testmon data: int)` | 0 | 395 | t1 41, t2 41, t3 301, t4 12 |  | 100.0% | 9.29 | 395 passed | 10.36 | 10.42 |
| 20 | a-z-combine | measure | `uv run pytest --testmon -q  (testmon data: z)` | 0 | 368 | t1 32, t2 23, t3 301, t4 12 |  | 100.0% | 9.27 | 368 passed, 18 deselected | 10.29 | 10.36 |
| 21 | a-z-combine | audit | `uv run pytest -q -p no:cacheprovider` | 0 |  |  |  |  | 3.59 | 409 passed | 4.27 | 4.37 |
| 22 | a-z-combine | audit | `uv run pytest acceptance --arm a --features b2g1,category_windows,coupons -q -p no:cacheprovider` | 0 |  |  |  |  |  | 128 passed | 0.81 | 0.82 |
| 23 | a-z-probe-config | probe | `uv run pytest --testmon -q  (testmon data: int)` | 0 | 0 |  |  |  | 0 |  | 0.42 | 0.44 |
| 24 | a-z-probe-config | probe | `uv run pytest -q -p no:cacheprovider --tb=line` | 1 |  |  |  |  |  | 215 failed, 194 passed | 2.57 | 2.59 |
| 25 | a-z-probe-coupons | probe | `uv run pytest --testmon -q  (testmon data: int)` | 0 | 0 |  |  |  | 0 |  | 0.42 | 0.44 |
| 26 | a-z-probe-coupons | probe | `uv run pytest -q -p no:cacheprovider --tb=line` | 1 |  |  |  |  |  | 1 failed, 408 passed | 3.8 | 3.82 |
| 27 | b-x-publish | agent | `uv run python ../estoppel gate --kind publish` | 0 | 9 | t1 9 | 435 | 0.0% | 0.01 | 9 passed, 435 deselected, 0 failed | 1.13 | 1.15 |
| 28 | b-x-publish | measure | `uv run pytest --testmon -q` | 0 | 9 | t1 9 |  | 0.0% | 0.01 | 9 passed | 0.52 | 0.53 |
| 29 | b-x-publish | agent | `git add -A && git commit -q -m "b2g1: publish the rule" -m "Estoppel-Kind: publish"` | 0 |  |  |  |  |  |  | 0.09 | 0.1 |
| 30 | b-x-activate | agent | `uv run python ../estoppel gate --kind activate` | 0 | 31 | t1 22, t4 9 | 414 | 0.5% | 0.05 | 31 passed, 414 deselected, 0 failed | 1.21 | 1.23 |
| 31 | b-x-activate | measure | `uv run pytest --testmon -q` | 0 | 1 | t4 1 |  | 0.0% | 0.0 | 1 passed | 0.51 | 0.53 |
| 32 | b-x-activate | agent | `git add -A && git commit -q -m "b2g1: activate the rule" -m "Estoppel-Kind: activate"` | 0 |  |  |  |  |  |  | 0.06 | 0.07 |
| 33 | b-y-publish | agent | `uv run python ../estoppel gate --kind publish` | 0 | 6 | t1 6 | 435 | 0.0% | 0.0 | 6 passed, 435 deselected, 0 failed | 1.11 | 1.14 |
| 34 | b-y-publish | measure | `uv run pytest --testmon -q` | 0 | 25 | t1 17, t4 8 |  | 0.0% | 0.02 | 25 passed, 14 deselected | 0.6 | 0.61 |
| 35 | b-y-publish | agent | `git add -A && git commit -q -m "category_windows: publish windows by category" -m "Estoppel-Kind: publish"` | 0 |  |  |  |  |  |  | 0.09 | 0.1 |
| 36 | b-y-modify | agent | `uv run python ../estoppel gate --kind modify` | 0 | 10 | t1 5, t4 5 | 433 | 0.0% | 0.01 | 10 passed, 433 deselected, 0 failed | 1.14 | 1.17 |
| 37 | b-y-modify | probe | `uv run python ../estoppel gate --kind activate` | 2 |  |  |  |  |  |  | 0.47 | 0.49 |
| 38 | b-y-modify | measure | `uv run pytest --testmon -q` | 0 | 27 | t1 17, t4 10 |  | 0.0% | 0.02 | 27 passed, 14 deselected | 0.62 | 0.63 |
| 39 | b-y-modify | agent | `git add -A && git commit -q -m "category_windows: use them in the refund policy" -m "Estoppel-Kind: modify"` | 0 |  |  |  |  |  |  | 0.06 | 0.07 |
| 40 | b-xy-combine | integrator | `uv run python ../estoppel combine scn/b-x scn/b-y` | 0 | 6 | t4 6 | 447 | 0.0% | 0.01 | 6 passed, 447 deselected, 0 failed | 3.21 | 3.38 |
| 41 | b-xy-combine | measure | `uv run pytest --testmon -q  (testmon data: base)` | 0 | 37 | t1 26, t4 11 |  | 0.0% | 0.02 | 37 passed, 14 deselected | 0.63 | 0.64 |
| 42 | b-xy-combine | measure | `uv run pytest --testmon -q  (testmon data: x)` | 0 | 28 | t1 17, t4 11 |  | 0.0% | 0.02 | 28 passed, 14 deselected | 0.6 | 0.61 |
| 43 | b-xy-combine | audit | `uv run pytest -q -p no:cacheprovider` | 0 |  |  |  |  | 5.79 | 453 passed | 6.44 | 6.48 |
| 44 | b-xy-combine | audit | `uv run pytest acceptance --arm b --features b2g1,category_windows -q -p no:cacheprovider` | 0 |  |  |  |  |  | 107 passed | 1.28 | 1.3 |
| 45 | b-xy-probe-config | probe | `uv run pytest --testmon -q  (testmon data: int)` | 0 | 0 |  |  |  | 0 |  | 0.43 | 0.45 |
| 46 | b-xy-probe-config | probe | `uv run python ../estoppel gate` | 1 |  |  |  |  |  | 9 failed, 11 passed, 433 deselected | 0.94 | 0.96 |
| 47 | b-xy-probe-config | probe | `uv run pytest -q -p no:cacheprovider --tb=line` | 1 |  |  |  |  |  | 9 failed, 444 passed | 6.41 | 6.45 |
| 48 | b-xy-probe-binding | probe | `uv run pytest --testmon -q  (testmon data: int)` | 0 | 0 |  |  |  | 0 |  | 0.44 | 0.45 |
| 49 | b-xy-probe-binding | probe | `uv run python ../estoppel gate` | 1 |  |  |  |  |  | 1 failed, 452 deselected | 0.87 | 0.89 |
| 50 | b-xy-probe-binding | probe | `uv run pytest -q -p no:cacheprovider --tb=line` | 1 |  |  |  |  |  | 1 failed, 452 passed | 6.33 | 6.37 |
| 51 | b-z-core | agent | `uv run python ../estoppel gate --kind modify` | 0 | 388 | t1 32, t2 46, t3 302, t4 8 | 53 | 97.4% | 6.87 | 388 passed, 53 deselected, 0 failed | 8.19 | 8.26 |
| 52 | b-z-core | probe | `uv run python ../estoppel gate --kind activate` | 2 |  |  |  |  |  |  | 0.48 | 0.51 |
| 53 | b-z-core | measure | `uv run pytest --testmon -q` | 0 | 392 | t1 36, t2 46, t3 302, t4 8 |  | 99.9% | 17.32 | 392 passed, 9 deselected | 17.97 | 18.56 |
| 54 | b-z-core | agent | `git add -A && git commit -q -m "coupons: budgets in the core" -m "Estoppel-Kind: modify"` | 0 |  |  |  |  |  |  | 0.1 | 0.14 |
| 55 | b-z-periphery | agent | `uv run python ../estoppel gate --kind modify` | 0 | 58 | t1 50, t4 8 | 396 | 2.5% | 0.06 | 58 passed, 396 deselected, 0 failed | 1.26 | 1.37 |
| 56 | b-z-periphery | probe | `uv run python ../estoppel gate --kind activate` | 2 |  |  |  |  |  |  | 0.48 | 0.5 |
| 57 | b-z-periphery | measure | `uv run pytest --testmon -q` | 0 | 46 | t1 38, t4 8 |  | 0.0% | 0.03 | 46 passed | 0.64 | 0.66 |
| 58 | b-z-periphery | agent | `git add -A && git commit -q -m "coupons: codes in the place-order workflow" -m "Estoppel-Kind: modify"` | 0 |  |  |  |  |  |  | 0.06 | 0.07 |
| 59 | b-z-publish | agent | `uv run python ../estoppel gate --kind publish` | 0 | 12 | t1 12 | 454 | 0.1% | 0.01 | 12 passed, 454 deselected, 0 failed | 1.2 | 1.22 |
| 60 | b-z-publish | measure | `uv run pytest --testmon -q` | 0 | 12 | t1 12 |  | 0.1% | 0.02 | 12 passed | 0.52 | 0.53 |
| 61 | b-z-publish | agent | `git add -A && git commit -q -m "coupons: publish the SAVE10 rule" -m "Estoppel-Kind: publish"` | 0 |  |  |  |  |  |  | 0.05 | 0.07 |
| 62 | b-z-activate | agent | `uv run python ../estoppel gate --kind activate` | 0 | 33 | t1 23, t4 10 | 435 | 2.5% | 0.11 | 33 passed, 435 deselected, 0 failed | 1.32 | 1.37 |
| 63 | b-z-activate | measure | `uv run pytest --testmon -q` | 0 | 6 | t1 4, t4 2 |  | 2.5% | 0.23 | 6 passed | 0.76 | 0.77 |
| 64 | b-z-activate | agent | `git add -A && git commit -q -m "coupons: activate SAVE10 in a new order stage" -m "Estoppel-Kind: activate"` | 0 |  |  |  |  |  |  | 0.06 | 0.07 |
| 65 | b-z-combine | integrator | `uv run python ../estoppel combine scn/b-z` | 3 |  |  |  |  |  |  | 2.75 | 2.91 |
| 66 | b-z-combine | integrator | `git merge -q --no-commit scn/b-z` | 1 |  |  |  |  |  |  | 0.08 | 0.1 |
| 67 | b-z-combine | integrator | `(copy the resolution's files)` | 0 |  |  |  |  |  |  | 0.01 | 0.01 |
| 68 | b-z-combine | integrator | `git add -A` | 0 |  |  |  |  |  |  | 0.04 | 0.04 |
| 69 | b-z-combine | integrator | `uv run python ../estoppel combine scn/b-z --resolved --decision "..."` | 0 | 55 | t1 42, t4 13 | 431 | 2.6% | 0.21 | 55 passed, 431 deselected, 0 failed | 4.36 | 4.57 |
| 70 | b-z-combine | measure | `uv run pytest --testmon -q  (testmon data: int)` | 0 | 444 | t1 83, t2 46, t3 302, t4 13 |  | 100.0% | 17.25 | 444 passed, 2 deselected | 18.34 | 18.56 |
| 71 | b-z-combine | measure | `uv run pytest --testmon -q  (testmon data: z)` | 0 | 41 | t1 28, t4 13 |  | 0.1% | 0.03 | 41 passed, 25 deselected | 0.69 | 0.78 |
| 72 | b-z-combine | audit | `uv run pytest -q -p no:cacheprovider` | 0 |  |  |  |  | 6.66 | 486 passed | 7.31 | 7.4 |
| 73 | b-z-combine | audit | `uv run pytest acceptance --arm b --features b2g1,category_windows,coupons -q -p no:cacheprovider` | 0 |  |  |  |  |  | 128 passed | 1.29 | 1.31 |
| 74 | b-z-probe-config | probe | `uv run pytest --testmon -q  (testmon data: int)` | 0 | 0 |  |  |  | 0 |  | 0.45 | 0.47 |
| 75 | b-z-probe-config | probe | `uv run python ../estoppel gate` | 1 |  |  |  |  |  | 9 failed, 11 passed, 466 deselected | 0.99 | 1.04 |
| 76 | b-z-probe-config | probe | `uv run pytest -q -p no:cacheprovider --tb=line` | 1 |  |  |  |  |  | 9 failed, 477 passed | 7.17 | 7.23 |
| 77 | b-z-probe-binding | probe | `uv run pytest --testmon -q  (testmon data: int)` | 0 | 0 |  |  |  | 0 |  | 0.44 | 0.45 |
| 78 | b-z-probe-binding | probe | `uv run python ../estoppel gate` | 1 |  |  |  |  |  | 2 failed, 42 passed, 442 deselected | 1.05 | 1.09 |
| 79 | b-z-probe-binding | probe | `uv run pytest -q -p no:cacheprovider --tb=line` | 1 |  |  |  |  |  | 2 failed, 484 passed | 7.09 | 7.13 |
| 80 | b-z-probe-coupons | probe | `uv run pytest --testmon -q  (testmon data: int)` | 0 | 0 |  |  |  | 0 |  | 0.44 | 0.45 |
| 81 | b-z-probe-coupons | probe | `uv run python ../estoppel gate` | 1 |  |  |  |  |  | 1 failed, 22 passed, 463 deselected | 0.98 | 1.02 |
| 82 | b-z-probe-coupons | probe | `uv run pytest -q -p no:cacheprovider --tb=line` | 1 |  |  |  |  |  | 1 failed, 485 passed | 7.15 | 7.19 |

| Branch | Lines changed by area |
|---|---|
| scn/a-x | rules and policies 7, tests 33 |
| scn/a-y | rules and policies 14, tests 52 |
| scn/a-int (X+Y) | rules and policies 21, tests 85 |
| scn/a-z | rules and policies 13, shared 29, tests 97 |
| scn/a-int (X+Y+Z) | rules and policies 34, shared 29, tests 182 |
| scn/b-x | claims (files) 29, periphery 15, tests 52 |
| scn/b-y | claims (files) 13, periphery 14, tests 47 |
| scn/b-int (X+Y) | claims (files) 49, periphery 29, tests 99 |
| scn/b-z | claims (files) 154, core 35, core tests 98, periphery 85, tests 135 |
| scn/b-int (X+Y+Z) | claims (files) 243, core 35, core tests 98, periphery 112, tests 234 |

| Arm | Files git could not merge at Z's combine |
|---|---|
| a | proto/m1/arm_a/checkout/config.py, proto/m1/arm_a/checkout/pricing.py, proto/m1/arm_a/tests/test_pricing.py |
| b | proto/m1/arm_b/checkout/app/config.py, proto/m1/arm_b/checkout/app/pricing/rules/__init__.py |
