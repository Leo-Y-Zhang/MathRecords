"""Mixed van der Waerden numbers -- engine used for the A217058 a(12) attempt.

    w(j+r; 2^j, t_1..t_r) = 1 + max{ n : [1,n] can be split into j "wildcard"
                                     singletons and r colour classes, class i
                                     containing no t_i-term arithmetic progression }

Lower bounds (SAT) are cheap and produce a colouring anybody can check by hand.
The matching upper bound (UNSAT) is where all the time goes, so that is what
this file is built around.  Three changes over vdw2:

1. REVERSAL SYMMETRY BREAKING.  vdw2's `_symbreak` only exchanges colours that
   share a target value, so for targets [3,4] -- the A217058 family -- it emits
   nothing at all and the search runs with no symmetry breaking whatsoever.
   But i -> n+1-i is always an automorphism: it maps t-term APs to t-term APs
   (a, a+d, .., a+(t-1)d  maps to  n+1-a-(t-1)d, .., n+1-a, same d), fixes the
   wildcard count and fixes every colour.  Requiring the colouring to be
   lexicographically <= its own reversal is therefore a sound lex-leader
   constraint that halves the search space.

2. PLUGGABLE ENGINE.  pysat here ships Kissat404 and Cadical300 as well as the
   Cadical195 vdw2 hardcoded; engine_bakeoff.py picks the fastest.
   Non-incremental engines are supported by baking the cube in as unit clauses
   instead of passing assumptions.

3. CRASH-HONEST PARALLELISM.  A worker killed by the OS must never be silently
   read as "this cube is UNSAT" -- that is exactly how a false new term gets
   published.  Every cube must return an explicit verdict or the whole run
   raises.

Soundness is not argued, it is tested: vdw_validate.py replays the published
values of five different target pairs through this engine and every SAT answer
is re-verified by `check`, which reads only the colouring and never the CNF.
"""
import itertools
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

from pysat.card import CardEnc, EncType
from pysat.formula import IDPool

DEFAULT_ENGINE = 'Cadical195'
# Solvers in pysat that do not implement the assumption interface; for these a
# cube is added as unit clauses and a fresh solver is built per cube.
NON_INCREMENTAL = {'Kissat404'}


def _solver(name):
    import pysat.solvers as ps
    return getattr(ps, name)


def aps(n, t):
    """Every t-term arithmetic progression inside [1,n]."""
    out = []
    for d in range(1, (n - 1) // (t - 1) + 1):
        for a in range(1, n - (t - 1) * d + 1):
            out.append([a + k * d for k in range(t)])
    return out


def build(n, j, targets, symbreak=True, revsym=True):
    """CNF for 'some legal colouring of [1,n] exists'.  Class 0 = wildcard."""
    r = len(targets)
    pool = IDPool()
    v = lambda i, c: pool.id(('v', i, c))
    cnf = []

    # exactly one class per position
    for i in range(1, n + 1):
        cnf.append([v(i, c) for c in range(r + 1)])
        for c1 in range(r + 1):
            for c2 in range(c1 + 1, r + 1):
                cnf.append([-v(i, c1), -v(i, c2)])

    # no monochromatic AP of the target length
    for c, t in enumerate(targets, start=1):
        for ap in aps(n, t):
            cnf.append([-v(i, c) for i in ap])

    # at most j wildcards
    cnf.extend(CardEnc.atmost(lits=[v(i, 0) for i in range(1, n + 1)], bound=j,
                              vpool=pool, encoding=EncType.totalizer).clauses)

    if symbreak:
        cnf.extend(_symbreak_colours(n, targets, pool, v))
    if revsym:
        cnf.extend(_symbreak_reversal(n, targets, pool, v))
    return cnf, pool, v


def _symbreak_colours(n, targets, pool, v):
    """Colours sharing a target value are interchangeable; force their first
    occurrences into increasing colour order.  Emits nothing when all targets
    are distinct (e.g. [3,4])."""
    r = len(targets)
    cls = []
    groups = {}
    for c, t in enumerate(targets, start=1):
        groups.setdefault(t, []).append(c)
    for t, cols in groups.items():
        if len(cols) < 2:
            continue
        for m in range(1, len(cols)):
            c_prev, c_cur = cols[m - 1], cols[m]
            p = [None] * (n + 2)
            for i in range(1, n + 2):
                p[i] = pool.id(('sb', t, m, i))
            cls.append([p[1]])
            for i in range(1, n + 1):
                cls.append([-p[i + 1], p[i]])
                cls.append([-p[i + 1], -v(i, c_prev)])
                cls.append([p[i + 1], -p[i], v(i, c_prev)])
                cls.append([-p[i], -v(i, c_cur)])
    return cls


def _symbreak_reversal(n, targets, pool, v):
    """Require class(1..n) <=_lex class(n..1).

    P[i] means "positions 1..i-1 all equal their mirror".  Given that, position
    i may not exceed its mirror.  Once some position is strictly below its
    mirror, P goes false and the rest is unconstrained.  Only i <= n//2 is
    needed: if every one of those equals its mirror the word is a palindrome
    and equals its own reversal, so the constraint holds automatically.
    """
    r = len(targets)
    cls = []
    half = n // 2
    if half == 0:
        return cls
    P = {i: pool.id(('rp', i)) for i in range(1, half + 2)}
    E = {i: pool.id(('re', i)) for i in range(1, half + 1)}
    cls.append([P[1]])
    for i in range(1, half + 1):
        m = n + 1 - i                                  # mirror position
        # E[i] <-> class(i) == class(m)   (both are one-hot, so pairwise suffices)
        for a in range(r + 1):
            cls.append([-E[i], -v(i, a), v(m, a)])
            cls.append([E[i], -v(i, a), -v(m, a)])
        # P[i] -> class(i) <= class(m):  forbid class(i)=a > class(m)=b
        for a in range(r + 1):
            for b in range(a):
                cls.append([-P[i], -v(i, a), -v(m, b)])
        # P[i+1] <-> P[i] and E[i]
        cls.append([-P[i + 1], P[i]])
        cls.append([-P[i + 1], E[i]])
        cls.append([P[i + 1], -P[i], -E[i]])
    return cls


def _has_mono_ap(prefix, targets):
    """Reject a cube whose fixed prefix already contains a monochromatic AP."""
    k = len(prefix)
    for c, t in enumerate(targets, start=1):
        pos = [i + 1 for i, x in enumerate(prefix) if x == c]
        ps = set(pos)
        for a in pos:
            for d in range(1, k):
                if a + (t - 1) * d <= k and all((a + m * d) in ps for m in range(t)):
                    return True
    return False


def make_cubes(n, j, targets, k, colour_sym=True):
    """Class assignments of positions 1..k surviving the local AP test, the
    wildcard budget and -- when `colour_sym` -- the colour-symmetry rule.

    **Set `colour_sym=False` for any certification run whose cube set must be
    provably exhaustive (`cube_exhaustive.py`).**  The colour-symmetry rule
    drops a prefix because some *other* prefix is its colour-permutation image,
    which is a sound way to search but is NOT a refutation: the dropped prefix
    is consistent with F, since the proofs deliberately run with symmetry
    breaking OFF (`build(..., symbreak=False)`).  The exhaustiveness walk then
    correctly reports it as an uncovered branch and fails closed.

    The rule is a no-op whenever the targets are pairwise distinct -- every
    group has one colour, so `cols[:len(seen)]` always matches -- which is why
    the A217058 family ([3, 4]) certified cleanly with it left on.  It bites
    exactly on the equal-target families, A217005 ([3, 3]) and A217007
    ([4, 4]).  Default stays True so the search path and the committed
    n=45 j=8 k=6 run keep their existing cube sets.
    """
    r = len(targets)
    groups = {}
    for c, t in enumerate(targets, start=1):
        groups.setdefault(t, []).append(c)
    cubes = []
    for pre in itertools.product(range(r + 1), repeat=k):
        if pre.count(0) > j:
            continue
        ok = True
        if colour_sym:
            for t, cols in groups.items():
                seen = []
                for x in pre:
                    if x in cols and x not in seen:
                        seen.append(x)
                if seen != cols[:len(seen)]:
                    ok = False
                    break
        if not ok or _has_mono_ap(pre, targets):
            continue
        cubes.append(pre)
    return cubes


def ap_incidence(n, targets):
    """inc[i] = how many target-length APs of [1,n] pass through position i,
    summed over the targets.  Positions near the centre lie on strictly more
    APs than positions near either end, so fixing them constrains more clauses
    per decision than fixing a prefix does."""
    inc = [0] * (n + 2)
    for t in targets:
        for ap in aps(n, t):
            for i in ap:
                inc[i] += 1
    return inc


def split_positions(n, k, mode='prefix', targets=None):
    """The k positions to split on.  'prefix' is the historical behaviour
    (positions 1..k); 'central' takes the middle window; 'incidence' takes the
    k positions of highest AP incidence (needs `targets`)."""
    if mode == 'prefix':
        return list(range(1, k + 1))
    if mode == 'central':
        lo = (n - k) // 2 + 1
        return list(range(lo, lo + k))
    if mode == 'incidence':
        if targets is None:
            raise ValueError("mode='incidence' needs targets")
        inc = ap_incidence(n, targets)
        return sorted(sorted(range(1, n + 1), key=lambda i: (-inc[i], i))[:k])
    raise ValueError(f'unknown split mode {mode!r}')


def _aps_within(n, targets, positions):
    """(colour, AP) pairs whose every member lies in `positions`."""
    S = set(positions)
    out = []
    for c, t in enumerate(targets, start=1):
        for ap in aps(n, t):
            if all(i in S for i in ap):
                out.append((c, ap))
    return out


def make_cubes_pos(n, j, targets, positions, colour_sym=False):
    """make_cubes generalised to an arbitrary SET of split positions.

    Returns cubes as tuples of (position, class) pairs.  A cube is dropped only
    when a clause already in build()'s output refutes it outright: a
    monochromatic target-length AP lying wholly inside `positions` (an AP
    clause), or more than j wildcards among them (the cardinality constraint).
    Everything else is kept, so the cube set stays EXHAUSTIVE: for any
    assignment of `positions`, it is either some cube or refuted by F alone.

    `colour_sym` is REFUSED off a prefix.  The repo's colour-symmetry rule
    orders the FIRST OCCURRENCE of interchangeable colours in the whole word;
    read off a window it orders first occurrences *within the window*, which is
    not a symmetry of F and silently deletes solutions.  Measured: [3,3] j=3
    n=19 is SAT, and a central k=6 window with that rule ported naively reports
    it UNSAT.  That is exactly how a false new term gets published.
    """
    positions = sorted(positions)
    k = len(positions)
    if colour_sym and positions != list(range(1, k + 1)):
        raise ValueError('colour_sym is sound only on a prefix; see docstring')
    r = len(targets)
    idx = {p: m for m, p in enumerate(positions)}
    within = [(c, [idx[i] for i in ap])
              for c, ap in _aps_within(n, targets, positions)]
    groups = {}
    for c, t in enumerate(targets, start=1):
        groups.setdefault(t, []).append(c)
    cubes = []
    for asg in itertools.product(range(r + 1), repeat=k):
        if asg.count(0) > j:
            continue
        if colour_sym:
            ok = True
            for t, cols in groups.items():
                seen = []
                for x in asg:
                    if x in cols and x not in seen:
                        seen.append(x)
                if seen != cols[:len(seen)]:
                    ok = False
                    break
            if not ok:
                continue
        if any(all(asg[m] == c for m in ap) for c, ap in within):
            continue
        cubes.append(tuple(zip(positions, asg)))
    return cubes


def _cube_pairs(cube):
    """Accept both cube shapes: a flat tuple of classes (legacy prefix cube,
    positions 1..k) or a tuple of (position, class) pairs."""
    if cube and isinstance(cube[0], tuple):
        return list(cube)
    return [(i + 1, c) for i, c in enumerate(cube)]


def _decode(model, v, n, r):
    m = set(l for l in model if l > 0)
    return [next(c for c in range(r + 1) if v(i, c) in m) for i in range(1, n + 1)]


def _cube_job(args):
    n, j, targets, cube, symbreak, revsym, engine = args
    cnf, pool, v = build(n, j, targets, symbreak=symbreak, revsym=revsym)
    r = len(targets)
    units = [[v(i, c)] for i, c in _cube_pairs(cube)]
    cls = _solver(engine)
    if engine in NON_INCREMENTAL:
        with cls(bootstrap_with=cnf + units) as s:
            if not s.solve():
                return None
            return _decode(s.get_model(), v, n, r)
    with cls(bootstrap_with=cnf) as s:
        if not s.solve(assumptions=[u[0] for u in units]):
            return None
        return _decode(s.get_model(), v, n, r)


def solve_direct(n, j, targets, conflicts=20_000, symbreak=True, revsym=True,
                 engine=DEFAULT_ENGINE):
    """One conflict-limited solver on the whole formula.
    Returns (True/False/None, colouring or None).  Kissat has no conflict
    budget in pysat, so it is never used for the probe."""
    if engine in NON_INCREMENTAL:
        engine = 'Cadical195'
    cnf, pool, v = build(n, j, targets, symbreak=symbreak, revsym=revsym)
    with _solver(engine)(bootstrap_with=cnf) as s:
        s.conf_budget(conflicts)
        r = s.solve_limited()
        if r is not True:
            return r, None
        return True, _decode(s.get_model(), v, n, len(targets))


def solve(n, j, targets, k=None, workers=16, symbreak=True, revsym=True,
          engine=DEFAULT_ENGINE, probe=20_000, split='prefix'):
    """(sat?, colouring or None).  Raises if any cube fails to report.

    `split` selects the cube positions: 'prefix' (default, unchanged) or
    'central'/'incidence' (see split_positions).  The non-prefix modes run with
    the colour-symmetry cube rule OFF, which is what a certification run needs
    anyway (cube_exhaustive.py)."""
    if probe:
        r, col = solve_direct(n, j, targets, conflicts=probe, symbreak=symbreak,
                              revsym=revsym, engine=engine)
        if r is True:
            return True, col
        if r is False:
            return False, None
    if k is None:
        k = 4 if len(targets) == 2 else 3
    if split == 'prefix':
        cubes = make_cubes(n, j, targets, k)
    else:
        cubes = make_cubes_pos(n, j, targets,
                               split_positions(n, k, split, targets))
    if not cubes:
        return False, None
    tasks = [(n, j, targets, c, symbreak, revsym, engine) for c in cubes]
    done = 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_cube_job, t) for t in tasks]
        try:
            for f in as_completed(futs):
                res = f.result()      # a dead worker raises here, never reads as UNSAT
                done += 1
                if res is not None:
                    return True, res
        finally:
            for f in futs:
                f.cancel()
    if done != len(tasks):
        raise RuntimeError(f'only {done}/{len(tasks)} cubes reported; UNSAT NOT proven')
    return False, None


def check(col, targets, j):
    """Independent verifier: reads only the colouring, never the CNF."""
    n = len(col)
    wild = sum(1 for c in col if c == 0)
    if wild > j:
        return False, wild, ('wildcard budget', wild, j)
    for c, t in enumerate(targets, start=1):
        pos = [i + 1 for i, x in enumerate(col) if x == c]
        ps = set(pos)
        for a in pos:
            for d in range(1, n):
                if a + (t - 1) * d > n:
                    break
                if all((a + m * d) in ps for m in range(t)):
                    return False, wild, ('mono AP', c, a, d)
    return True, wild, None


if __name__ == '__main__':
    n, j = int(sys.argv[1]), int(sys.argv[2])
    targets = [int(a) for a in sys.argv[3:]]
    t0 = time.time()
    ok, col = solve(n, j, targets)
    print(f'n={n} j={j} {targets}: {"SAT" if ok else "UNSAT"}  {time.time()-t0:.2f}s')
    if ok:
        print('  verify:', check(col, targets, j))
