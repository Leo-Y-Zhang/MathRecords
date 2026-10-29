from fractions import Fraction as F

import pytest

import verify_rank as rank


CURVE = [0, 0, 1, -7, 6]
P = (F(0), F(2))
Q = (F(4), F(6))


def test_real_rank_witness_and_one_changed_coordinate():
    problems, info = rank.verify(CURVE, [P], lo=3, hi=4)
    assert problems == []
    assert info['k'] == 1
    problems, _ = rank.verify(CURVE, [(0, 3)], lo=3, hi=4)
    assert any('not on the curve' in p for p in problems)


def test_singular_curve_and_exactly_dependent_points_are_rejected():
    assert any('singular' in p for p in rank.verify([0] * 5, [(0, 0)])[0])
    problems, info = rank.verify(CURVE, [P, P])
    assert any('exact relation' in p for p in problems)
    assert info['relation'] is not None


def test_torsion_is_rejected_even_without_the_small_relation_search():
    problems, _ = rank.verify([0, -1, 1, -10, -20], [(5, 5)],
                              lo=3, hi=4, bound=0)
    assert any('torsion' in p for p in problems)


@pytest.mark.parametrize(('low', 'high', 'floor', 'decay_tol', 'message'), [
    ([[1.0]], [[0.25]], 0.25, 10, 'torsion'),
    ([[1.0]], [[0.25]], 0.01, 4, 'torsion'),
    ([[1.0, 0.5], [0.5, 1.0]], [[1.0, 0.5], [0.5, 1.0]],
     0.75, 10, 'regulator'),
    ([[1.0, 0.0], [0.0, 1.0]], [[1.0, 0.5], [0.5, 1.0]],
     0.01, 4 / 3, 'decays'),
])
def test_numerical_rejection_boundaries(monkeypatch, low, high, floor, decay_tol, message):
    # Isolate the numerical policy with exact, hand-built matrices. Group law,
    # on-curve validation and the relation search still run on real points.
    monkeypatch.setattr(rank.E, 'gram', lambda self, pts, iters: low if iters == 3 else high)
    points = [P] if len(low) == 1 else [P, Q]
    problems, _ = rank.verify(CURVE, points, lo=3, hi=4,
                              floor=floor, decay_tol=decay_tol)
    assert any(message in p for p in problems)


def test_exact_group_law_handles_identity_inverse_and_doubling():
    curve = rank.E(*CURVE)
    twice = (F(49, 25), F(-32, 125))
    assert curve.add(None, P) == curve.add(P, None) == P
    assert curve.add(P, curve.neg(P)) is None
    assert curve.add(P, P) == twice
    assert curve.on(twice)
    assert curve.mul(2, P) == twice
    assert curve.mul(-2, P) == curve.neg(twice)
    assert curve.mul(0, P) is None


def test_determinant_pivot_sign_and_nonpositive_heights():
    assert rank._det([[0, 2], [3, 4]]) == -6
    assert rank._det([[1, 2], [2, 4]]) == 0
    assert rank._norm([[0]], 1) == 0
    assert rank._norm([[-1]], 1) == 0
