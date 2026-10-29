import json

import pytest

import make_submit_pack as pack


def write_record(directory, name, record):
    (directory / name).write_text(json.dumps(record), encoding='utf-8')


def test_crosscheck_is_bound_to_index_targets_and_value(monkeypatch, tmp_path):
    monkeypatch.setattr(pack, 'VDW', str(tmp_path))
    record = {'j': 1, 'targets': [3, 4], 'claim': 21, 'AGREES': True}
    write_record(tmp_path, 'crosscheck_a1.json', record)
    assert pack.crosscheck('A217058', [3, 4], 1, 21)[0] == record
    for key, wrong in [('j', 2), ('targets', [3, 3]), ('claim', 22)]:
        write_record(tmp_path, 'crosscheck_a1.json', {**record, key: wrong})
        assert pack.crosscheck('A217058', [3, 4], 1, 21)[0] is None


@pytest.mark.parametrize('field', ['seq', 'j', 'w', 'PASS', 'sat_at_w_minus_1', 'unsat_at_w'])
def test_validation_gate_requires_every_part_of_the_previous_term(monkeypatch, tmp_path, field):
    monkeypatch.setattr(pack, 'VDW', str(tmp_path))
    record = {'seq': 'A217058', 'j': 0, 'w': 18, 'PASS': True,
              'sat_at_w_minus_1': True, 'unsat_at_w': True}
    write_record(tmp_path, 'validate_small.json', [record])
    assert pack.family_gate('A217058', [3, 4], [18], 1) is not None
    record.pop(field)
    write_record(tmp_path, 'validate_small.json', [record])
    assert pack.family_gate('A217058', [3, 4], [18], 1) is None


def test_probe_gate_requires_both_sides_and_an_authenticated_witness(monkeypatch, tmp_path):
    monkeypatch.setattr(pack, 'VDW', str(tmp_path))
    low = {'j': 0, 'targets': [3, 4], 'n': 17, 'sat': True, 'witness_verified': True}
    high = {'j': 0, 'targets': [3, 4], 'n': 18, 'sat': False}
    write_record(tmp_path, 'probe_gate_low.json', low)
    assert pack.family_gate('A217058', [3, 4], [18], 1) is None
    write_record(tmp_path, 'probe_gate_high.json', high)
    assert pack.family_gate('A217058', [3, 4], [18], 1) is not None
    for key, wrong in [('j', 1), ('targets', [4, 4]), ('n', 16),
                       ('sat', False), ('witness_verified', False)]:
        write_record(tmp_path, 'probe_gate_low.json', {**low, key: wrong})
        assert pack.family_gate('A217058', [3, 4], [18], 1) is None


def test_truncated_evidence_is_not_accepted(monkeypatch, tmp_path):
    monkeypatch.setattr(pack, 'VDW', str(tmp_path))
    (tmp_path / 'crosscheck_a1.json').write_text('{"j": 1,', encoding='ascii')
    with pytest.raises(json.JSONDecodeError):
        pack.crosscheck('A217058', [3, 4], 1, 21)
