import itertools
from concurrent.futures import Future
from concurrent.futures.process import BrokenProcessPool

import pytest

import vdw4


def test_internal_checker_accepts_witness_and_rejects_corruptions():
    assert vdw4.check([0, 1, 1, 2], [3, 4], 1) == (True, 1, None)
    assert vdw4.check([0, 0, 1, 2], [3, 4], 1)[0] is False
    assert vdw4.check([1, 1, 1, 2], [3, 4], 1)[0] is False
    assert vdw4.check([1, 2, 2, 2, 2], [3, 4], 0)[0] is False


@pytest.mark.parametrize('bad_colour', [-1, 3])
def test_internal_checker_rejects_out_of_range_colours(bad_colour):
    assert vdw4.check([bad_colour, 1, 2], [3, 4], 0)[0] is False


def test_all_aps_include_maximum_step_and_endpoint():
    assert vdw4.aps(5, 3) == [[1, 2, 3], [2, 3, 4], [3, 4, 5], [1, 3, 5]]
    assert vdw4.aps(2, 3) == []


def test_plain_encoding_exactly_matches_small_assignments():
    # At n=3, j=0 the cardinality constraint has no auxiliary variables.
    # Evaluate every Boolean assignment, including missing/multiple colours,
    # directly against the clauses; no SAT solver or production checker oracle.
    cnf, pool, v = vdw4.build(3, 0, [3, 3], symbreak=False, revsym=False)
    assert pool.top == 9
    for bits in itertools.product((False, True), repeat=9):
        one_hot = [sum(bits[v(i, c) - 1] for c in range(3)) == 1
                   for i in range(1, 4)]
        expected = (all(one_hot)
                    and not any(bits[v(i, 0) - 1] for i in range(1, 4))
                    and not any(all(bits[v(i, c) - 1] for i in range(1, 4))
                                for c in (1, 2)))
        actual = all(any(bits[abs(lit) - 1] == (lit > 0) for lit in clause)
                     for clause in cnf)
        assert actual == expected, bits


def test_nonprefix_cubes_preserve_both_colour_orders_and_budget_boundary():
    cubes = set(vdw4.make_cubes_pos(7, 1, [3, 3], [2, 4, 6]))
    expected = {tuple(zip((2, 4, 6), colours))
                for colours in itertools.product(range(3), repeat=3)
                if colours.count(0) <= 1 and colours not in ((1, 1, 1), (2, 2, 2))}
    assert cubes == expected
    assert ((2, 2), (4, 1), (6, 2)) in cubes
    with pytest.raises(ValueError, match='only on a prefix'):
        vdw4.make_cubes_pos(7, 1, [3, 3], [2, 4, 6], colour_sym=True)


def test_non_ap_split_positions_do_not_prune_a_monochromatic_assignment():
    cubes = vdw4.make_cubes_pos(7, 0, [3], [1, 2, 4])
    assert cubes == [((1, 1), (2, 1), (4, 1))]


def test_prefix_cubes_can_disable_colour_symmetry_for_certification():
    assert set(vdw4.make_cubes(2, 0, [3, 3], 2, colour_sym=False)) == {
        (1, 1), (1, 2), (2, 1), (2, 2)}
    assert set(vdw4.make_cubes(2, 0, [3, 3], 2)) == {(1, 1), (1, 2)}


def test_split_and_decode_use_one_based_positions():
    assert vdw4.split_positions(8, 3, 'central') == [3, 4, 5]
    assert vdw4.split_positions(5, 2, 'incidence', [3]) == [1, 3]
    with pytest.raises(ValueError):
        vdw4.split_positions(5, 2, 'incidence')
    with pytest.raises(ValueError):
        vdw4.split_positions(5, 2, 'unknown')
    _, _, v = vdw4.build(2, 0, [3, 3], symbreak=False, revsym=False)
    assert vdw4._decode([-v(1, 0), v(1, 2), v(2, 1)], v, 2, 2) == [2, 1]


def install_cube_workers(monkeypatch, outcomes, omit_last=False):
    """Complete futures locally; never construct a solver or spawn workers."""
    futures = []
    for outcome in outcomes:
        future = Future()
        if isinstance(outcome, Exception):
            future.set_exception(outcome)
        else:
            future.set_result(outcome)
        futures.append(future)

    class Executor:
        def __init__(self, **kwargs):
            self.pending = iter(futures)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def submit(self, function, task):
            return next(self.pending)

    monkeypatch.setattr(vdw4, 'ProcessPoolExecutor', Executor)
    monkeypatch.setattr(vdw4, 'make_cubes', lambda *args: [(1,), (2,)])
    monkeypatch.setattr(vdw4, 'as_completed',
                        lambda submitted: iter(submitted[:-1] if omit_last else submitted))


@pytest.mark.parametrize(('outcomes', 'expected'), [
    ([None, None], (False, None)),
    ([None, [1, 2]], (True, [1, 2])),
])
def test_cube_search_requires_explicit_results(monkeypatch, outcomes, expected):
    install_cube_workers(monkeypatch, outcomes)
    assert vdw4.solve(2, 0, [3, 3], k=1, probe=0) == expected


def test_dead_cube_worker_cannot_be_read_as_unsat(monkeypatch):
    install_cube_workers(monkeypatch, [BrokenProcessPool('worker died'), None])
    with pytest.raises(BrokenProcessPool, match='worker died'):
        vdw4.solve(2, 0, [3, 3], k=1, probe=0)


def test_missing_cube_result_cannot_be_read_as_unsat(monkeypatch):
    install_cube_workers(monkeypatch, [None, None], omit_last=True)
    with pytest.raises(RuntimeError, match='1/2 cubes reported; UNSAT NOT proven'):
        vdw4.solve(2, 0, [3, 3], k=1, probe=0)
