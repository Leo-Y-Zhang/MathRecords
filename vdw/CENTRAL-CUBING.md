# Central-position cubing for vdw4 — what it is, what it is worth

Private notes. Nothing here has been committed, pushed or published; the repo at
`/home/user/mathrecords` was never modified (`git status --porcelain` empty at start and
at finish). The patch lives beside this file as `central-cubing.patch` and applies to
`vdw/vdw4.py` (`git apply --check` passes).

Every number below was measured in this session on this machine, single-threaded,
in-process, with pysat's `Cadical195` and `s.accum_stats()`. Conflicts and propagations
are deterministic; wall-clock numbers are flagged where the box was shared.

## Verdict in one paragraph

The premise is essentially right and the patch's own claim reproduces: splitting on
central positions instead of a prefix costs **1.50x–3.66x fewer conflicts** across five
UNSAT instances in two families (2.10x–3.66x at k=6), and 3.24x fewer at the repo's
headline configuration (n=45, j=8, [3,4], k=6). But the honest baseline kills it as a way
to compute values: **cube-and-conquer with central splitting still costs 1.61x–5.30x more
conflicts than simply solving the formula monolithically**, at every size tested. Central splitting does not
turn cubing into a win, it makes a self-inflicted regression smaller. It is worth having
for the **certification path**, where per-cube proofs are mandatory and the monolithic
solve is not an option; there the patch cuts total proof work by ~3x and the hardest
single cube by 3.2x. It is not a way to reach a(13) faster.

One wall-clock caveat that cuts the other way is recorded in §7 — do not skip it.

## 1. What the patch does

`vdw/vdw4.py` currently splits on the first k **positions**: `make_cubes()` enumerates
all class assignments of positions 1..k, drops a prefix that already contains a
monochromatic target-length AP, that blows the wildcard budget, or (optionally) that
violates the colour-symmetry rule.

The patch adds, without touching `make_cubes()` or any existing default:

- `ap_incidence(n, targets)` — how many target-length APs pass through each position.
- `split_positions(n, k, mode, targets)` — `'prefix'` (unchanged behaviour),
  `'central'` (the middle window of k positions), `'incidence'` (the k positions of
  highest AP incidence).
- `make_cubes_pos(n, j, targets, positions, colour_sym=False)` — `make_cubes()`
  generalised to an arbitrary **set** of split positions. Cubes come back as tuples of
  `(position, class)` pairs. A cube is dropped only when a clause already in `build()`'s
  output refutes it: a monochromatic AP lying wholly inside the split positions, or more
  than j wildcards among them.
- `_cube_pairs()` — accepts both cube shapes, so `_cube_job()` is a one-line change and
  legacy flat prefix cubes keep working unchanged.
- `solve(..., split='prefix')` — new keyword; `'central'`/`'incidence'` route through
  `make_cubes_pos`. Default behaviour is bit-for-bit what it was.

`colour_sym=True` is **refused** off a prefix. See §4; this is the one place where a
careless port of the existing code would produce a false term.

## 2. The premise: AP incidence (claim partly confirmed, numbers corrected)

Claimed: central positions carry far more AP incidence than a prefix — "248 vs 144 at
t=3 and 212 vs 105 at t=4" at n=45.

Measured at n=45, k=6 (sum over the six positions of the number of t-term APs through
each):

| | t=3 | t=4 |
|---|---|---|
| prefix, positions 1..6 | **144** | **105** |
| central, positions 20..25 | **252** | **213** |
| claimed central | 248 | 212 |

The prefix figures reproduce **exactly**. The central figures do not: I measure 252 and
213. I swept every contiguous 6-window at n=45. **No window at t=3 sums to 248** — the
maximum over all 40 windows is 252, attained at 20..25 and 21..26. At t=4, 212 does
occur, but only at the off-centre windows 15..20 and 26..31; every window from 17..22
through 23..28 gives exactly 213, and 213 is the maximum. So one claimed figure is
unattainable and the other belongs to a window that is not central. The direction and
rough size of the effect (1.75x at t=3, 2.03x at t=4) are right, the figures are not.
Do not quote 248/212; the central k=6 values at n=45 are 252 and 213.

Full profile at n=45, t=3: incidence rises 22, 22, 24, 24, ... to 44 at position 23 and
falls symmetrically. At t=4 it rises from 14 to ~36 and plateaus, oscillating between 35
and 36 over the middle third — which is why 'central' and 'incidence' pick nearly the
same positions and behave nearly identically everywhere below.

## 3. Cube sets are exhaustive and sound (checked, not argued)

- **Tautology over the split positions.** For every configuration tried, I enumerated all
  (r+1)^k assignments of the split positions and classified each one: it is a cube, or it
  is refuted by a named clause of F (a monochromatic AP inside the split set, or the
  wildcard cardinality bound). Zero uncovered branches, zero cubes kept that F refutes.
  Checked at n=45 j=8 [3,4] for k=4, 6, 8 in all three modes (e.g. k=6 central:
  603 cubes + 126 AP-drops + 0 budget-drops = 729 = 3^6), and with a tight budget to
  exercise the cardinality drop (n=45 j=3 k=8 central: 2914 + 2074 + 1573 = 6561), plus
  n=35 j=2 [3,3] k=7 and n=55 j=4 [4,5] k=6 with a non-contiguous incidence set.
- **Cubes are pairwise disjoint** over the split positions (no assignment in two cubes).
- **Known witness lands in exactly one cube.** The n=44 j=8 [3,4] SAT colouring
  (verified by `check`: 8 wildcards, no mono AP) falls in exactly 1 of the 603 cubes for
  prefix, central and incidence splitting.
- **Prefix mode is byte-identical to the repo.** `make_cubes_pos` on positions 1..k
  returns exactly `make_cubes(..., colour_sym=False)` across 2520 configurations
  (5 target pairs x n in 10..49 x j in 0..8 x k in 3..6), 0 mismatches.

## 4. The trap: do not port the colour-symmetry rule to a window

`make_cubes()`'s `colour_sym` rule orders the **first occurrences** of interchangeable
colours. That is a statement about the whole word. Read off a central window it orders
first occurrences *within the window*, which is not a symmetry of F — a colouring may
legitimately start colour 1 outside the window and colour 2 inside it.

This is not hypothetical. Measured: **[3,3] j=3 n=19 is SAT** (monolithic solve, 33
conflicts; A217005 a(3)=20 so n=19 must be SAT). With a central k=6 window and the rule
ported naively, plus the formula's own colour-swap symmetry breaking, the cube set
returns **UNSAT** — a lost solution, i.e. exactly the failure mode that publishes a false
new term. With `build(symbreak=False)` the same cube set returns SAT, which is why the
bug can hide: it only bites when both symmetry breakings are on.

The patch therefore raises `ValueError` if `colour_sym=True` is requested off a prefix.
Non-prefix splitting always runs with the rule off, which is what certification requires
anyway.

## 5. Correctness: 13 OEIS rungs across four families, 0 disagreements

Each rung solved through the cube path with the monolithic probe disabled, at k=6, in
prefix and central modes (plus incidence on the first six rungs); every SAT answer
re-verified by `check()`, which reads the colouring only and never the CNF.

| family | j | a(j) | n=a(j)-1 | n=a(j) |
|---|---|---|---|---|
| A217058 [3,4] | 0,1,2,3,4,5 | 18,21,25,29,33,36 | SAT (verified) | UNSAT |
| A217005 [3,3] | 0,1,4,5 | 9,14,21,24 | SAT (verified) | UNSAT |
| A217007 [4,4] | 0,1 | 35,40 | SAT (verified) | UNSAT |
| A217059 [3,5] | 0 | 22 | SAT (verified) | UNSAT |

Plus the two big ones used for benchmarking: n=44 j=8 [3,4] SAT (verified, 8 wildcards)
and n=45 j=8 [3,4] UNSAT, 2486 clauses, 1,396,228 conflicts — matching the recorded
baseline exactly.

13 rungs, i.e. 26 instances (each a(j)-1 and a(j)). The first six rungs ([3,4] j=0..3,
[3,3] j=0,1) were run in all three modes, the remaining seven in prefix and central:
64 solved instances in total, 0 disagreements with OEIS and 0 failed `check()`
verifications.

## 6. Benchmark (a): central vs the repo's prefix cubing — the claim holds

Sum of conflicts and propagations over the whole cube set, every cube solved (no early
exit), fresh solver per cube with the cube as assumptions, i.e. the repo's own
`_cube_job` shape.

| instance | k | split | cubes | conflicts (sum) | propagations (sum) | vs prefix | vs monolithic |
|---|---|---|---|---|---|---|---|
| **n=33 j=5 [3,3]** | - | **monolithic (no cubes)** | - | 4,710 | 235,763 | - | 1.00x |
| n=33 j=5 [3,3] | 4 | prefix | 71 | 18,958 | 1,019,491 | 1.00x | 4.03x worse |
| n=33 j=5 [3,3] | 4 | central | 71 | 10,568 | 598,164 | 1.79x | 2.24x worse |
| n=33 j=5 [3,3] | 4 | incidence | 71 | 10,568 | 598,164 | 1.79x | 2.24x worse |
| n=33 j=5 [3,3] | 6 | prefix | 522 | 40,803 | 2,266,556 | 1.00x | 8.66x worse |
| n=33 j=5 [3,3] | 6 | central | 522 | 19,419 | 1,130,300 | 2.10x | 4.12x worse |
| n=33 j=5 [3,3] | 6 | incidence | 510 | 19,640 | 1,151,517 | 2.08x | 4.17x worse |
| **n=35 j=6 [3,3]** | - | **monolithic (no cubes)** | - | 9,117 | 437,345 | - | 1.00x |
| n=35 j=6 [3,3] | 4 | prefix | 71 | 34,635 | 1,886,134 | 1.00x | 3.80x worse |
| n=35 j=6 [3,3] | 4 | central | 71 | 23,151 | 1,350,224 | 1.50x | 2.54x worse |
| n=35 j=6 [3,3] | 4 | incidence | 71 | 22,770 | 1,351,656 | 1.52x | 2.50x worse |
| n=35 j=6 [3,3] | 6 | prefix | 523 | 99,458 | 5,711,974 | 1.00x | 10.91x worse |
| n=35 j=6 [3,3] | 6 | central | 523 | 44,041 | 2,684,316 | 2.26x | 4.83x worse |
| n=35 j=6 [3,3] | 6 | incidence | 523 | 44,041 | 2,684,316 | 2.26x | 4.83x worse |
| **n=40 j=6 [3,4]** | - | **monolithic (no cubes)** | - | 175,224 | 6,410,524 | - | 1.00x |
| n=40 j=6 [3,4] | 4 | prefix | 75 | 1,485,102 | 64,414,700 | 1.00x | 8.48x worse |
| n=40 j=6 [3,4] | 4 | central | 75 | 712,483 | 34,247,977 | 2.08x | 4.07x worse |
| n=40 j=6 [3,4] | 4 | incidence | 75 | 712,483 | 34,247,977 | 2.08x | 4.07x worse |
| n=40 j=6 [3,4] | 6 | prefix | 603 | 3,818,704 | 197,439,174 | 1.00x | 21.79x worse |
| n=40 j=6 [3,4] | 6 | central | 603 | 1,043,755 | 61,068,250 | 3.66x | 5.96x worse |
| n=40 j=6 [3,4] | 6 | incidence | 603 | 1,043,755 | 61,068,250 | 3.66x | 5.96x worse |
| **n=42 j=7 [3,4]** | - | **monolithic (no cubes)** | - | 913,916 | 27,457,287 | - | 1.00x |
| n=42 j=7 [3,4] | 4 | prefix | 75 | 3,488,334 | 141,802,768 | 1.00x | 3.82x worse |
| n=42 j=7 [3,4] | 4 | central | 75 | 1,474,177 | 66,045,152 | 2.37x | 1.61x worse |
| n=42 j=7 [3,4] | 4 | incidence | 75 | 1,474,177 | 66,045,152 | 2.37x | 1.61x worse |
| n=42 j=7 [3,4] | 6 | prefix | 603 | 10,508,539 | 479,222,774 | 1.00x | 11.50x worse |
| n=42 j=7 [3,4] | 6 | central | 603 | 3,022,063 | 168,689,654 | 3.48x | 3.31x worse |
| n=42 j=7 [3,4] | 6 | incidence | 603 | 3,022,063 | 168,689,654 | 3.48x | 3.31x worse |
| **n=45 j=8 [3,4]** | - | **monolithic (no cubes)** | - | 1,396,228 | 42,924,439 | - | 1.00x |
| n=45 j=8 [3,4] | 4 | prefix | 75 | 8,424,168 | 327,348,082 | 1.00x | 6.03x worse |
| n=45 j=8 [3,4] | 4 | central | 75 | 2,984,075 | 130,827,127 | 2.82x | 2.14x worse |
| n=45 j=8 [3,4] | 4 | incidence | 76 | 2,946,820 | 128,255,068 | 2.86x | 2.11x worse |
| n=45 j=8 [3,4] | 6 | prefix | 603 | 23,980,575 | 1,031,616,290 | 1.00x | 17.18x worse |
| n=45 j=8 [3,4] | 6 | central | 603 | 7,402,577 | 363,200,098 | 3.24x | 5.30x worse |
| n=45 j=8 [3,4] | 6 | incidence | 597 | 7,554,095 | 368,396,939 | 3.17x | 5.41x worse |

Central beats prefix in all ten comparisons: **1.50x–2.82x at k=4** (median 2.08x) and
**2.10x–3.66x at k=6** (median 3.24x). The reported "~2.10x" is in range — it is exactly
what I measure at k=4 on n=40 [3,4] (2.08x) and at k=6 on n=33 [3,3] (2.10x); at the
headline n=45 j=8 k=6 the gain is larger, 3.24x, and at the smallest [3,3] instance at
k=4 it is only 1.50x.

`incidence` is not distinguishable from `central`: it picks the same or nearly the same
positions and lands within 2% everywhere. Not worth the extra code path on its own; it
is in the patch because it costs three lines and generalises to targets whose incidence
profile is not symmetric.

**Why it works, and a caveat on the explanation.** A control at n=40 j=6 [3,4] k=4,
varying only the split positions:

| positions | AP incidence | conflicts |
|---|---|---|
| 1,2,3,4 (prefix) | 140 | 1,485,102 |
| 37,38,39,40 (suffix) | 140 | 1,036,244 |
| 4,14,33,38 (random) | 186 | 1,177,417 |
| 5,7,24,35 (random) | 197 | 1,107,832 |
| 4,10,21,26 (random) | 226 | 914,304 |
| 10,11,12,13 (quarter) | 230 | 913,548 |
| 19,20,21,22 (central) | 276 | **712,483** |

Conflicts fall broadly with incidence (the ordering is monotone once the two
equal-incidence endpoints are set aside) — but note the suffix: same incidence as the
prefix, 1.43x fewer conflicts. So incidence is not the whole story. Part of the prefix's
weakness is that it overlaps the reversal lex-leader constraint, which already pins down
the front of the word; fixing those same positions buys less new information. I did not
chase this further, and the write-up should not claim incidence is the sole mechanism.

## 7. Benchmark (b): central cubing vs just solving it — the honest baseline

Same table, last column. Against a single monolithic `Cadical195` call on the same
formula:

| instance | monolithic | best cubing (central/incidence) | cubing penalty |
|---|---|---|---|
| n=33 j=5 [3,3] | 4,710 | 10,568 (k=4) | 2.24x worse |
| n=35 j=6 [3,3] | 9,117 | 22,770 (k=4) | 2.50x worse |
| n=40 j=6 [3,4] | 175,224 | 712,483 (k=4) | 4.07x worse |
| n=42 j=7 [3,4] | 913,916 | 1,474,177 (k=4) | 1.61x worse |
| n=45 j=8 [3,4] | 1,396,228 | 2,946,820 (k=4) | 2.11x worse |
| n=45 j=8 [3,4] | 1,396,228 | 7,402,577 (k=6) | 5.30x worse |

In conflicts, cubing loses at every size tested, with or without the patch. The patch
narrows the loss (at n=45 k=6, from 17.2x to 5.3x) but never closes it. Deeper cubing is
worse, not better: k=6 costs 2.5x the conflicts of k=4 in central mode at n=45.

**The wall-clock caveat.** Conflicts are not seconds. Measured serially on an otherwise
idle box, n=45 j=8 [3,4]:

| run | conflicts | wall |
|---|---|---|
| monolithic (rep 1) | 1,396,228 | 79.8s |
| monolithic (rep 2) | 1,396,228 | 78.6s |
| central k=4, 75 cubes | 2,984,075 | **55.9s** |
| central k=6, 603 cubes | 7,402,577 | 114.9s |
| prefix k=4, 75 cubes | 8,424,168 | 212.6s |
| prefix k=6, 603 cubes | 23,980,575 | 472.6s |

So at k=4, central cubing runs ~1.4x **faster** in wall-clock than the monolithic solve
despite 2.1x more conflicts: a cube's conflicts are cheaper than the monolithic run's,
whose learnt-clause database grows large. Single-threaded and at this one size. That is
one data point against my own summary, and it is the one worth re-testing before
anybody concludes cubing is useless here: with 4 workers the k=4 central cube path would
plausibly beat the monolithic solve outright in wall-clock. I did not measure the
parallel path (the repo's `ProcessPoolExecutor`), and the per-cube CNF rebuild in
`_cube_job` is included in these timings.

The conflict-count statement ("cubing is a net loss") is therefore solid only as a
statement about search work, not about elapsed time.

## 8. Where it does help: certification

`cube_certify.py` needs a DRAT proof per cube — the monolithic solve is not an
alternative there, the per-cube work must happen. For that path the patch is a real,
unambiguous gain:

- total per-cube work at n=45 j=8 k=6: 23,980,575 -> 7,402,577 conflicts (3.24x).
- hardest single cube at n=45 j=8 k=4: 323,555 -> 101,494 conflicts (3.19x). That is the
  quantity that sets the makespan and the largest proof file.
- 4-core LPT makespan over the same cube set: 2,113,920 -> 752,196 conflicts (2.81x).

**Limitation, not yet done.** The patch changes the search path only. `cube_certify.py`
and `cube_exhaustive.py` both call `make_cubes()` directly, parse cubes as flat class
tuples, and walk a prefix tree. Using central cubes for a certification run requires
extending those two files to the `(position, class)` shape and relabelling the tree walk.
That generalisation looks mechanical — the tree is the same (r+1)-ary tree with different
variable labels — but it is **not implemented and not tested here**, and the
exhaustiveness DRAT tail in particular must be re-derived and re-checked before any
certified value is claimed with central cubes.

## 9. Plain statement of when to use it

- Computing a new value of one of these sequences: **use the monolithic solve**
  (`solve_direct`, or `solve(..., probe=...)` with a large budget). Cubing, prefix or
  central, costs more search. The patch does not change that.
- Running the certification pipeline, where per-cube proofs are mandatory: **use
  `split='central'`**, k=4 rather than k=6, after extending the two certification tools.
  Expect ~3x less total work and ~3x smaller hardest cube.
- Never enable `colour_sym` with a non-prefix split. The patch refuses it; if you port
  this code anywhere else, keep that refusal.
- Do not quote the incidence figures 248/212; they are 252/213.

## 10. Reproducing

Scripts used, all in `/tmp/claude-0/-home-user-Blank/cdf10545-c83e-52b1-ab18-ba0699ae1f41/scratchpad/cc/`:
`incid.py`, `incid2.py` (§2), `central.py` (the implementation, mirrored by the patch),
`exhaust.py`, `exhaust2.py`, `equiv.py` (§3), `csym_hazard.py` (§4), `rungs.py`,
`rungs2.py` (§5), `driver.py`, `bench_mid.py`, `bench45.py`, `control.py` (§6),
`makespan.py` (§8), `clean_wall.py`, `clean_wall2.py` (§7). Raw logs: `bench_mid.log`,
`bench45.log`.

Environment: python 3.11.15, python-sat 1.9.dev15, Cadical195, 4 cores, 15 GB.
