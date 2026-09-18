# The sigma-equivariance trap: a symmetric constraint with an asymmetric encoding

Private note. Nothing here has been published, filed, or sent anywhere.
Every number below was measured in this session by
`/tmp/claude-0/-home-user-Blank/cdf10545-c83e-52b1-ab18-ba0699ae1f41/scratchpad/private-drafts/sigma_check.py`
and its companions (`sigma_drat.py`, `sigma_drat2.py`, `sigma_drat3.py`,
`sigma_scan.py`, `sigma_acid.py`). Nothing is copied from a previous run.

---

## READ THIS FIRST: the published values are NOT affected

**No published term of A217058, A217005, A217007, A217059 or A217236 is put in
doubt by anything in this note.** The finding is about a *proof-engineering*
technique that was never used to produce them.

Two independent lines of evidence, both measured here.

**(1) Verdicts are identical with and without the reversal lex-leader.**
16 rungs — j = 0..3 for `[3,4]` (A217058) and `[3,3]` (A217005), each at both
`n = a(j) - 1` (should be SAT) and `n = a(j)` (should be UNSAT) — solved three
ways: `(symbreak=False, revsym=False)`, `(True, False)`, `(True, True)`.
48 full solves, Cadical195, no cube split, no conflict budget.

- disagreements between the three configurations: **0 / 16 rungs**
- verdicts matching the published sequences: **16 / 16**
- SAT witnesses re-verified by `vdw4.check` (reads only the colouring): **all pass**

**(2) sigma is a semantic symmetry of the formula, cube by cube, exhaustively.**
Over 6 instances and **2052 cubes total**, comparing `sat(F & cube)` against
`sat(F & sigma(cube))` with `F` built symmetry-breaking-**off**:

| instance | cubes | cubes where the two verdicts differ |
|---|---:|---:|
| n=24 j=2 `[3,4]` k=6 | 376 | **0** |
| n=28 j=3 `[3,4]` k=6 | 530 | **0** |
| n=33 j=4 `[3,4]` k=5 | 212 | **0** |
| n=19 j=3 `[3,3]` k=6 | 450 | **0** |
| n=16 j=2 `[3,3]` k=6 | 302 | **0** |
| n=20 j=3 `[3,3]` k=5 | 182 | **0** |

Perfect agreement, 2052 for 2052.

This is the whole point, and it is worth stating precisely because it is easy to
scare oneself with the headline finding below:

> The paper's reversal argument is about the **colouring**, not about the CNF.
> Reversal maps valid colourings to valid colourings (it sends a *t*-term AP to a
> *t*-term AP and fixes the wildcard count), so requiring `colouring <=_lex
> reversal(colouring)` keeps at least one representative of every orbit and
> therefore preserves satisfiability. **That argument never needed sigma to be an
> automorphism of the CNF.** A lex-leader constraint needs the symmetry to act on
> the *solution set*; it does not care how the auxiliary variables are wired.

So the headline finding is a real property of the encoding and a real obstacle to
one specific *optimisation*, and it has no bearing on the published numbers.

---

## The finding: sigma is not a CNF automorphism

Let `sigma : v(i,c) -> v(n+1-i, c)`, identity on every auxiliary variable.
Build with `symbreak=False, revsym=False` so only the raw encoding is present.
Clauses canonicalised as sorted tuples of distinct literals.

| instance | clauses | `|F \ sigma(F)|` | `|sigma(F) \ F|` | automorphism? |
|---|---:|---:|---:|---|
| n=14 j=3 `[3,4]` | 270 | **24** | **24** | No |
| n=45 j=8 `[3,4]` | 2221 | **86** | **86** | No |

Both counts reproduce exactly. (For reference, with `symbreak=True, revsym=True`
the same two instances are 355 and 2486 clauses; 96 / 386 variables raw.)

### Attribution, demonstrated rather than asserted

Each block tested separately for closure under sigma:

| block | n=14 clauses | offenders | sigma-closed? | n=45 clauses | offenders | sigma-closed? |
|---|---:|---:|---|---:|---:|---|
| exactly-one | 56 | **0** | yes | 180 | **0** | yes |
| AP | 68 | **0** | yes | 799 | **0** | yes |
| cardinality (totalizer) | 146 | **24** | **no** | 1242 | **86** | **no** |

The exactly-one and AP blocks *together* form a sigma-invariant set (checked
directly: `True` at both sizes). Every clause of the symmetric difference — 48
clauses at n=14, 172 at n=45 — lies in the totalizer block or is a sigma-image of
one. **Confirmed: every offender is a totalizer clause.**

The cause is exactly as suspected. The constraint "at most *j* of the `v(i,0)`
are true" is completely symmetric in its inputs. The *totalizer* is not: pysat
builds a binary counting tree over the literal list in the order given, and each
internal node's auxiliary variables mean "at least *m* of *this subtree's*
positions." Reversing positions permutes which positions sit under which node,
but sigma leaves the auxiliary variables alone, so the mirrored clause talks
about the old subtree with the new positions. The semantics survive; the syntax
does not.

### The repair works exactly

Build the totalizer over the **reversed** literal list, same pool, v-variables
allocated in the same order:

| instance | forward clauses | reversed clauses | `sigma(forward) == reversed`? |
|---|---:|---:|---|
| n=14 j=3 | 146 | 146 | **True** |
| n=45 j=8 | 1242 | 1242 | **True** |

Exact clause-set equality, both sizes. (The forward totalizer is of course not
sigma-invariant on its own — `False` — which is the finding restated.)

So a sigma-equivariant encoding is available for free: emit both orderings, or
choose an encoding whose auxiliary structure is itself mirror-symmetric. That is
the precondition any per-cube proof-transport scheme would need.

---

## The second claim did NOT survive: drat-trim is not wrongly accepting anything

The sharper claim was: renaming a DRAT proof under sigma yields an **invalid**
proof that drat-trim nevertheless **accepts** (reported 9 of 12). The observable
half reproduces. The interpretation does not, and I could not make it fail in
any way that convicts the checker.

**Setup.** `drat-trim` binary already present in this scratchpad, built from
upstream `drat-trim.c` with `sha256 = d834b649f437e091597f5347f259b9f681087f89ca0844d0cee250a1a1a0c2ee`,
matching the hash recorded in `vdw/DRAT.md`. I could not re-download and
re-compile it in this session (blocked), so it is reused, not rebuilt.
Checker controls run here: real proof vs UNSAT formula → `VERIFIED`; the same
proof vs a satisfiable formula → `NOT VERIFIED`; bare empty clause → `NOT
VERIFIED`. (A fourth "bogus lemma" control I wrote was not actually bogus — the
lemma was genuinely RAT — so drat-trim was right to accept it. My error, noted
so it is not mistaken for a checker fault.)

**Correction to `DRAT.md`.** That file says pysat returns a truncated proof from
*every* solver it ships. Measured here: `Cadical195`, `Cadical153` and
`Cadical103` return **0 proof lines**, as described — but **`Glucose4` emits a
complete proof ending in the empty clause** on these formulas, and drat-trim
verifies it. All proofs below come from Glucose4.

**Why the first result was vacuous.** Transporting proofs at n=25, j=2, `[3,4]`,
k=5 gave **12 of 12 renamed proofs `VERIFIED`** — which looks alarming until you
notice that `F` *itself* is UNSAT at n=25. Every cube target is UNSAT, so
`VERIFIED` is a true verdict and no wrong acceptance is possible. That
experiment cannot detect the thing it was meant to detect.

**On a satisfiable base formula** (n=24, j=2, `[3,4]`, k=6, 120 cubes with
transportable proofs), the pass rate is real but the failures are too:

| renaming | target UNSAT → VERIFIED | target UNSAT → NOT VERIFIED | target SAT → VERIFIED |
|---|---:|---:|---:|
| sigma (reversal) | 88 | 32 | **0** |
| rho (cyclic shift by 1) | 72 | 48 | **0** |

So ~73% of sigma-renamed proofs still check — comparable to the reported 9/12 —
but **every single acceptance is on a genuinely unsatisfiable target.** Nothing
false was certified.

**The acid test.** The only way to convict the checker is to hand it a renamed
proof whose target is *satisfiable*. `rho`, a cyclic shift, is deliberately not
a symmetry (APs wrap around the boundary). Scanning the 2052 cubes above found
**17 cubes where `F & cube` is UNSAT but `F & rho(cube)` is SAT**. Transporting
the UNSAT proof onto the SAT target in each case:

| outcome | count |
|---|---:|
| drat-trim `VERIFIED` (would certify a falsehood) | **0** |
| drat-trim `NOT VERIFIED` (correct rejection) | **17** |

**17 of 17 correctly rejected.**

**Conclusion.** The claim "the renamed proofs are invalid but drat-trim accepts
them" is **refuted as stated**. A DRAT proof *is* valid exactly when each lemma
is RAT against the accumulated formula and the empty clause is derived — which
is what drat-trim checks. When sigma-renaming produces an accepted proof here,
the proof genuinely is valid and the target genuinely is unsatisfiable, because
sigma is a semantic symmetry (evidence: 2052/2052 above). When a renaming is
*not* a semantic symmetry and the target is actually satisfiable, drat-trim
catches it every time. There is no checker bug in evidence, and I would not
write one up.

What *is* true, and is the only defensible version of the claim:

> Naive literal renaming under sigma is an **unreliable** proof-transport
> shortcut, not an unsound one. 32 of 120 transported proofs failed to check
> here, because the totalizer's auxiliary variables are not mirror-equivariant
> and the renamed lemmas about them no longer propagate. Transport that is
> *supposed* to work requires a sigma-equivariant cardinality encoding
> (the reversed-input totalizer above gives one exactly).

---

## The precondition, stated once

Per-cube proof transport under a geometric symmetry `s` of a problem needs two
separate things, and they are easy to conflate:

1. **`s` is a symmetry of the solution set.** This is what a lex-leader
   symmetry-breaking constraint needs, and it is what `vdw4`'s reversal argument
   establishes. It is about the colouring. **This holds here.**
2. **`s` is an automorphism of the CNF**, i.e. the encoding is `s`-equivariant
   including its auxiliary variables. This is what *renaming a proof* needs.
   **This does not hold here**, and the sole reason is the totalizer's fixed
   left-to-right tree.

Condition 1 without condition 2 is the normal situation for any encoding with
order-dependent auxiliary structure — totalizer, sequential counter, commander,
most BDD-based cardinality encodings. Failing condition 2 costs you the
*optimisation*. It does not cost you the *result*, and it does not make a
checker unsound: the checker re-derives everything from the formula it is given
and does not know or care that a renaming was involved.

The trap is assuming that because the mathematics is reversal-symmetric, the CNF
is too.

---

## Caveats

- `drat-trim` was reused from an earlier session's build rather than rebuilt here
  (network fetch and compile were blocked). Its hash matches upstream and it
  passed the three negative controls listed above, but I did not compile it
  myself in this session.
- Proof emission worked only via `Glucose4`; the Cadical family returns empty
  proofs through pysat, so the transport results rest on one solver's proofs.
- Step 4 covers j = 0..3 in two families (16 rungs, 48 solves). It does not
  reach the large j where the published headline terms live; the argument that
  those are unaffected is the structural one in part (2) plus the cube scan,
  not an exhaustive re-solve of the sequences.
- The rho control found 17 danger cubes in 4 instances. Absence of a wrong
  acceptance in 17 cases is strong but is not a proof that drat-trim has no such
  bug.

---

## Appendix: baseline re-measured, so the build path is known to be the right one

Single-threaded, in-process, Cadical195, `symbreak=True, revsym=True`,
no cube split, no conflict budget:

| instance | verdict | clauses | conflicts | wall |
|---|---|---:|---:|---:|
| n=44 j=8 `[3,4]` | SAT | 2395 | 61,398 | 1.3 s |
| n=45 j=8 `[3,4]` | UNSAT | 2486 | 1,396,228 | 79.0 s |

The conflict counts are deterministic and load-independent; the wall times on
this box are not, and the 79.0 s should be read as "same order", not as a
measurement. This is here only to confirm that the formulas analysed above are
the same formulas the project actually solves.
