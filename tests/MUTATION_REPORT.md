# Mutation-guided unit tests

The tests cover the active colouring checker and encoding, cube composition,
proof verdict dispatch, rank verifier, evidence parsers, and the parallel
search's decision to report UNSAT. No import seam or runtime dependency was
added. The CI gate job now installs pytest 8.4.2 and runs `pytest -q`.

## Bugs found and fixed

The measurement found two verifier defects; both are fixed in this change and
each fix has a test that was seen failing against the old code.

- **DRAT verdicts matched a substring.** `drat_certify.certify`,
  `cube_certify.certify_cube` and `cube_exhaustive.check_tail` all tested
  `'s VERIFIED' in out` before `'s NOT VERIFIED'`, so a failed replay whose
  output also contained the text `s VERIFIED` (in a comment, say) was recorded
  as VERIFIED, and output with no status line at all but that text was
  accepted. All three now read whole status lines and check failure first.
  CI's `drat` job replays the real proofs through the fixed code.
- **`vdw4.check` ignored colours outside the alphabet.** A colouring with a
  colour below 0 or above the number of targets skipped the
  monochromatic-AP scan for those cells and could be accepted. It now rejects
  any cell that is not 0 (wildcard) or a target colour.

## Measurement

Before means the existing **full** `python verify_all.py` gate, including its
encoding and scale audits. After means that gate plus the new pytest suite.
Each of the 54 mutants changes one source site in an isolated disposable copy.
All compile and none time out. The original sources are never mutated.

| Module | Mutants tried | Killed before | Killed after |
|---|---:|---:|---:|
| `vdw/verify_certificate.py` | 6 | 4 | 6 |
| `vdw/vdw4.py` | 15 | 5 | 15 |
| `vdw/cube_exhaustive.py` | 8 | 2 | 8 |
| `vdw/drat_certify.py` | 5 | 0 | 5 |
| `vdw/cube_certify.py` | 6 | 4 | 6 |
| `ec/verify_rank.py` | 8 | 2 | 8 |
| `make_submit_pack.py` | 6 | 0 | 6 |
| **Total** | **54** | **17** | **54** |

This is a targeted first-order mutation sample, not exhaustive mutation
coverage. Without kissat and drat-trim the local gate skips its real
external-proof checks; the unit tests check verdict dispatch with mocked tool
output, not the mathematical validity of DRAT proofs.

Each test file kills meaningful survivors:

| Test file | Example mutant killed, at the original source location |
|---|---|
| `test_certificate.py` | C02, `vdw/verify_certificate.py:55`: replace `if bad:` with `if False:`, accepting unknown symbols. C06 also changes the returned wildcard count by one. |
| `test_vdw_core.py` | V15, `vdw/vdw4.py:395`: skip the new colour-range check, so colours -1 and 3 are accepted. V12, `vdw/vdw4.py:383`: flip `done != len(tasks)` to `==`, losing the missing-result guard. V14 ignores `f.result()`, hiding dead workers. Also checks CNF truth tables, AP endpoints, cube pruning and decoding. |
| `test_cube_exhaustive.py` | E04, `vdw/cube_exhaustive.py:146`: return before recording an uncovered branch. E05, line 274: disable the formula-hash rejection predicate. Valid covers pass; a removed cube, a removed AP clause and a truncated record fail. |
| `test_proof_verdicts.py` | D03, `vdw/drat_certify.py:170`: match `s VERIFIED` anywhere in the output again (E07 and P04 do the same in `cube_exhaustive.py` and `cube_certify.py`); only the comment-line rows catch these. P06, `vdw/cube_certify.py`: report the formula hash as the proof hash. Includes accepted proofs, truncation, SAT, tool errors, timeouts, wrong cube counts and DIMACS clause counts. |
| `test_rank.py` | R03, `ec/verify_rank.py:208`: change the height floor from `<=` to `<`. Tests also kill equality-boundary mutations in decay and regulator checks; real points, corrupted coordinates, singular curves, dependent points and torsion are exercised. |
| `test_evidence.py` | S01, `make_submit_pack.py:87`: disable the cross-check index comparison. Also rejects wrong targets/value, missing gate fields, incomplete probe pairs and truncated JSON. |

`conftest.py` only makes the script directories importable. `mutation_check.py`
is the standard-library mutation harness; `mutation_results.json` records each
mutation, source line, before/after exit status and failing pytest node IDs.
The test-local ignore file excludes temporary logs. The harness reproduces
the full current experiment with:

```sh
.venv/bin/python tests/mutation_check.py --jobs 4
```

The measurement used that command and selected reruns with `--only E05` and
`--jobs 3 --only V12 V13 V14`; the final results contain 53 unique single-site
mutants, merged by ID. Per-mutant after measurements run the full pytest suite
again. This slower experiment is separate from CI and the fast unit suite.

## Commands and results

Measured on a real checkout with Python 3.13 (the CI version), pytest 8.4.2
and python-sat 1.9.dev7:

| Command | Result |
|---|---|
| `python tests/mutation_check.py --jobs 4` | 54 tried; 17 killed before, 54 after |
| `pytest -q` | 77 passed in 0.29 s |
| `python verify_all.py` | 135 passed, 0 failed, 25 skipped (needs kissat, drat-trim) |
| `python scrub_paths.py --check` | 0 files carry machine-local paths |
| `git diff --check` | Clean |

No unit test runs a SAT solver, starts worker processes or uses the network.
