import itertools
import json

import pytest

import cube_exhaustive as exhaustive
from vdw4 import build


def small_cover():
    cnf, _, v = build(3, 1, [3, 3], symbreak=False, revsym=False)
    cubes = {c for c in itertools.product(range(3), repeat=3)
             if c.count(0) <= 1 and c not in ((1, 1, 1), (2, 2, 2))}
    return cubes, cnf, v


def test_valid_cover_and_a_removed_cube():
    cubes, cnf, v = small_cover()
    report, lemmas = exhaustive.compose(3, 1, [3, 3], 3, cubes, cnf, v)
    assert report['counterexamples'] == []
    assert report['unmatched_cubes'] == []
    assert report['stats']['cube'] == 18
    assert report['stats']['dropped_mono_ap'] == 2
    assert report['stats']['dropped_up'] > 0
    assert lemmas[-1] == []
    report, _ = exhaustive.compose(3, 1, [3, 3], 3,
                                   cubes - {(1, 2, 1)}, cnf, v)
    assert [1, 2, 1] in [c['prefix'] for c in report['counterexamples']]


def test_an_ap_is_not_a_refutation_if_its_clause_is_missing():
    cubes, cnf, v = small_cover()
    cnf.remove([-v(i, 1) for i in (1, 2, 3)])
    report, _ = exhaustive.compose(3, 1, [3, 3], 3, cubes, cnf, v)
    assert any(c['prefix'] == [1, 1, 1] and 'clause absent' in c['why']
               for c in report['counterexamples'])


@pytest.mark.parametrize(('cnf', 'assumptions', 'expected'), [
    ([], [1, -1], 'conflict'),
    ([[]], [], 'conflict'),
    ([[-2, 3], [-1, 2], [-3]], [1], 'conflict'),
    ([[1, 2], [-1, 2]], [], 'stable'),
    ([[1, 2], [-2]], [1], 'stable'),
    ([[-1, -2]], [1, 2], 'conflict'),
])
def test_unit_propagation_requires_a_real_conflict(cnf, assumptions, expected):
    assert exhaustive.unit_propagate(cnf, assumptions)[0] == expected


def test_records_must_be_verified_against_the_same_formula(tmp_path):
    path = tmp_path / 'results.jsonl'
    record = {'cube': [1, 2, 1], 'verdict': 'VERIFIED', 'formula_sha256': 'correct'}
    path.write_text(json.dumps(record) + '\n', encoding='ascii')
    assert exhaustive.load_cubes(str(path), 3, 'correct') == ([(1, 2, 1)], 0, 0)
    assert exhaustive.load_cubes(str(path), 3, 'wrong') == ([(1, 2, 1)], 1, 1)
    record['verdict'] = 'NOT_VERIFIED'
    path.write_text(json.dumps(record) + '\n', encoding='ascii')
    assert exhaustive.load_cubes(str(path), 3, 'correct') == ([(1, 2, 1)], 1, 0)


def test_a_truncated_record_cannot_cover_a_missing_branch(tmp_path):
    cubes, cnf, v = small_cover()
    victim = (1, 2, 1)
    path = tmp_path / 'results.jsonl'
    records = [json.dumps({'cube': c, 'verdict': 'VERIFIED', 'formula_sha256': 'f'})
               for c in sorted(cubes - {victim})]
    # The resumable loader ignores a torn final line; composition must still
    # reject its absent cube rather than certify the remaining records.
    path.write_text('\n'.join(records) + '\n{"cube": [1, 2,', encoding='ascii')
    loaded, _, _ = exhaustive.load_cubes(str(path), 3, 'f')
    report, _ = exhaustive.compose(3, 1, [3, 3], 3, set(loaded), cnf, v)
    assert list(victim) in [c['prefix'] for c in report['counterexamples']]
