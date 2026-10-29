import hashlib
import subprocess
from pathlib import Path

import pytest

import cube_certify
import cube_exhaustive
import drat_certify


PROOF = b'1 0\n0\n'


def install_tools(monkeypatch, solver_code=20, checker_output='s VERIFIED\n',
                  checker_code=0, timeout_at=None):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert kwargs['timeout'] == 0.1
        tool = command[0]
        assert tool in ('fake-kissat', 'fake-trim')
        if tool == timeout_at:
            raise subprocess.TimeoutExpired(command, kwargs['timeout'])
        if tool == 'fake-kissat':
            Path(command[-1]).write_bytes(PROOF)
            return subprocess.CompletedProcess(command, solver_code, '', 'solver diagnostic')
        output = checker_output
        if output is None:
            output = ('s VERIFIED\n' if Path(command[-1]).read_bytes() == PROOF
                      else 's NOT VERIFIED\n')
        return subprocess.CompletedProcess(command, checker_code, output, 'checker diagnostic')

    monkeypatch.setattr(subprocess, 'run', run)
    return calls


def certify(kind, tmp_path, truncate=False):
    if kind == 'cube':
        return cube_certify.certify_cube(
            (3, 1, [3, 3], (1, 2, 1), str(tmp_path),
             'fake-kissat', 'fake-trim', 0.1, truncate))
    return drat_certify.certify(
        3, 1, [3, 3], {'kissat': 'fake-kissat', 'drat_trim': 'fake-trim'},
        str(tmp_path), timeout=0.1)


@pytest.mark.parametrize('kind', ['cube', 'whole'])
@pytest.mark.parametrize(('solver_code', 'output', 'checker_code', 'expected'), [
    (20, 's VERIFIED\n', 1, 'VERIFIED'),
    (20, 's NOT VERIFIED\n', 0, 'NOT_VERIFIED'),
    (20, '', 0, 'SOLVER_ERROR'),
    (20, 'checker diagnostic only\n', 0, 'SOLVER_ERROR'),
    # Only a whole status line counts, and failure wins over a stray success.
    (20, 'c previous s VERIFIED result\n', 0, 'SOLVER_ERROR'),
    (20, 'c previous s VERIFIED result\ns NOT VERIFIED\n', 0, 'NOT_VERIFIED'),
    (10, 's VERIFIED\n', 0, 'SAT'),
    (1, 's VERIFIED\n', 0, 'SOLVER_ERROR'),
])
def test_only_an_explicit_checker_verdict_certifies(
        monkeypatch, tmp_path, kind, solver_code, output, checker_code, expected):
    calls = install_tools(monkeypatch, solver_code, output, checker_code)
    record = certify(kind, tmp_path)
    assert record['verdict'] == expected
    assert len(calls) == (2 if solver_code == 20 else 1)


@pytest.mark.parametrize('kind', ['cube', 'whole'])
@pytest.mark.parametrize('stage', ['fake-kissat', 'fake-trim'])
def test_timeouts_are_not_refutations(monkeypatch, tmp_path, kind, stage):
    install_tools(monkeypatch, timeout_at=stage)
    assert certify(kind, tmp_path)['verdict'] == 'TIMEOUT'


def test_truncating_a_proof_rejects_it_and_hashes_the_actual_bytes(monkeypatch, tmp_path):
    install_tools(monkeypatch, checker_output=None)
    accepted = certify('cube', tmp_path)
    assert accepted['verdict'] == 'VERIFIED'
    assert accepted['proof_sha256'] == hashlib.sha256(PROOF).hexdigest()
    rejected = certify('cube', tmp_path, truncate=True)
    assert rejected['verdict'] == 'NOT_VERIFIED'
    assert rejected['proof_sha256'] == hashlib.sha256(PROOF[:len(PROOF) // 2]).hexdigest()
    assert Path(rejected['kept_files'][1]).read_bytes() == PROOF[:len(PROOF) // 2]


@pytest.mark.parametrize(('output', 'expected'), [
    ('s VERIFIED\n', 'VERIFIED'),
    ('s NOT VERIFIED\n', 'NOT_VERIFIED'),
    ('', 'CHECKER_ERROR'),
    ('c previous s VERIFIED result\n', 'CHECKER_ERROR'),
    ('c previous s VERIFIED result\ns NOT VERIFIED\n', 'NOT_VERIFIED'),
])
def test_composition_tail_dispatch_and_written_clause_counts(
        monkeypatch, tmp_path, output, expected):
    install_tools(monkeypatch, checker_output=output)
    result = cube_exhaustive.check_tail(
        '1 2 0', 2, 1, {(1,), (2,)}, [[-1], []], lambda i, c: c,
        'fake-trim', str(tmp_path), timeout=0.1)
    assert result['verdict'] == expected
    assert (tmp_path / 'fprime.cnf').read_text() == 'p cnf 2 3\n1 2 0\n-1 0\n-2 0\n'
    assert (tmp_path / 'tail.drat').read_text() == '-1 0\n0\n'
    assert result['fprime_clauses'] == 3
    assert result['tail_lemmas'] == 2


def test_dimacs_preserves_signs_empty_clauses_and_counts(tmp_path):
    clauses = [[1, -2], [], [3]]
    path = tmp_path / 'formula.cnf'
    drat_certify.write_dimacs(clauses, 3, path)
    assert path.read_text() == 'p cnf 3 3\n1 -2 0\n 0\n3 0\n'
    assert cube_certify.dimacs_body(clauses) == '1 -2 0\n 0\n3 0'


def test_cube_parser_accepts_both_separators_and_rejects_wrong_counts():
    assert cube_certify.parse_cube('1, 0 2', 3) == (1, 0, 2)
    for text in ('1,0', '1,0,2,1', ''):
        with pytest.raises(SystemExit, match='entries, expected'):
            cube_certify.parse_cube(text, 3)
    with pytest.raises(ValueError):
        cube_certify.parse_cube('1,x,2', 3)
