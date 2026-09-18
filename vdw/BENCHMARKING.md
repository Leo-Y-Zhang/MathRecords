# Benchmarking on this family: the clause-order noise floor

Short version: on these instances, permuting the clause order of a formula — which
changes nothing about what the formula means — moves the conflict count by more than a
factor of two. Any speedup claim below that, measured one run per configuration, is
not evidence.

This file exists because several performance claims in this repository were made that
way, and have been withdrawn. The mathematical results are untouched; see the end.

## The measurement

Take the CNF from `vdw4.build(n, j, targets, symbreak=True, revsym=True)` and shuffle
the clause list before handing it to the solver. Same clauses, same variable numbering,
same literals. Only the order changes, which changes CaDiCaL's initial variable scores,
phase saving and watch-list layout.

`n = 45, j = 8, targets [3,4]` — the benchmark refutation. 2486 clauses, Cadical195,
single-threaded, in-process, **16 clause permutations**, all returning UNSAT:

| | conflicts |
|---|---|
| min | 887,582 |
| median | 1,359,012 |
| max | 2,005,413 |
| **max / min** | **2.26** |

Conflict counts are deterministic — rerunning the same `(instance, mode, seed)`
reproduces them exactly — so the spread is the permutation and nothing else.

Other instances: 1.56× at `n=42, j=7`; 2.15× at `n=37, j=11`; 1.56× at `n=31, j=8`.
Not solver-specific: Cadical153 1.61×, Glucose4 1.40×, Minisat22 1.70×. Variable
renaming, a different null transformation, gives 1.58×–1.93×.

**The satisfiable side is far worse.** `n = 44, j = 8`, 24 permutations:
19,766 → 719,703 conflicts, a spread of **36.4×**.

## What it costs

Bootstrapping from the 16 samples, two configurations that are *genuinely identical*,
each scored as a median of *k* permutations, still appear to differ by:

| protocol | median apparent ratio | 95th percentile |
|---|---|---|
| one run each | 1.26× | **1.89×** |
| median of 3 | 1.20× | 1.59× |
| median of 5 | 1.17× | 1.50× |
| median of 9 | 1.12× | 1.41× |

Even a median-of-9 protocol manufactures a 1.4× "speedup" from nothing one time in
twenty. Below roughly 1.4× there is no repeat count that rescues a single-instance
claim; you need many instances, or a mechanism argument.

## The claim this retired

`PAPER.md` §4.4 reported a 1.55× speedup from the reversal lex-leader constraint.
Measured distributionally instead — 12 clause permutations per configuration on the
monolithic path, all 24 runs UNSAT:

| | N | min | median | max |
|---|---|---|---|---|
| `revsym=True` | 12 | 887,582 | 1,386,901 | 2,005,413 |
| `revsym=False` | 12 | 1,009,244 | 1,194,370 | 2,117,652 |

Median ratio 0.861 — the *opposite* sign. Permutation test on the median difference,
200,000 relabelings: two-sided **p = 0.347**. The luckiest single pair in this data
would have reported 2.39×, the unluckiest 0.50×. 1.55× sits unremarkably inside that.

Nothing went wrong in the original experiment except that its sample size was one.

Caveat: the original 1.55× was measured through the full `solve()` path (cube-and-
conquer, process pool, wall clock). The table above is the monolithic single-solver
path scored in conflicts. So this establishes that there is no detectable effect on
the monolithic path, and that the original protocol could not have established one
either way. It does **not** establish that the constraint fails to pay in the cube
setting — that was not re-run.

## Protocol to use instead

Time both configurations over the *same set* of clause permutations and compare
distributions, not single runs. Report conflicts, not wall clock: conflicts are
deterministic, wall clock on a shared machine is not. State the sample size.

`vdw/revsym_bench.py` and `vdw/engine_bakeoff.py` both predate this and both report
single runs. Treat anything they print below ~2.3× as noise.

## What is not affected

Every published term rests on a refutation plus an explicitly checked witness. How long
a proof took has no bearing on whether it is a proof, and the lex-leader argument in
§4.4 is a proof of soundness, not a measurement. No value in this repository, and no
OEIS term, is touched by anything on this page. What is affected is the performance
claims — and those are the ones most likely to be repeated by someone else.
