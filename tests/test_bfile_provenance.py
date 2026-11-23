"""The b-file rows after a claimed term belong to other people.

Since October 2026 the OEIS entries carry terms added by other contributors,
and the committed b-files carry them too so that they match the OEIS. The gate
accepts those rows only as oeis_provenance.json records them: contiguous after
the claimed term, value for value, each under the EXTENSIONS line that credits
it, and never credited to this repository's author.
"""
import verify_all

AUTHOR = 'A. Author'


def record(lo, hi, values, contributor='B. Other', extensions=None):
    span = f'a({lo})' if lo == hi else f'a({lo})-a({hi})'
    return {'indices': [lo, hi], 'values': values, 'contributor': contributor,
            'extensions': extensions or f'{span} from _{contributor}_, Nov 05 2026'}


def test_recorded_terms_follow_the_claim_in_order():
    provenance = {'A217058': [record(13, 14, [58, 61]), record(15, 15, [63])]}
    rows, problems = verify_all.others_terms('A217058', 12, provenance, AUTHOR)
    assert problems == []
    assert rows == [(13, 58), (14, 61), (15, 63)]


def test_a_sequence_with_nothing_recorded_has_no_rows():
    assert verify_all.others_terms('A217058', 12, {}, AUTHOR) == ([], [])


def test_a_gap_after_the_claimed_term_is_reported():
    provenance = {'A217058': [record(14, 14, [61])]}
    _rows, problems = verify_all.others_terms('A217058', 12, provenance, AUTHOR)
    assert any('a(14)' in p and 'a(13)' in p for p in problems)


def test_a_range_and_its_values_must_have_the_same_length():
    provenance = {'A217058': [record(13, 15, [58, 61])]}
    _rows, problems = verify_all.others_terms('A217058', 12, provenance, AUTHOR)
    assert any('3 indices' in p and '2 values' in p for p in problems)


def test_a_term_credited_to_this_repositorys_author_is_reported():
    provenance = {'A217058': [record(13, 13, [58], contributor=AUTHOR)]}
    _rows, problems = verify_all.others_terms('A217058', 12, provenance, AUTHOR)
    assert any('author' in p for p in problems)


def test_the_extensions_line_must_name_the_contributor_and_the_range():
    for line in ('a(13)-a(14) from _C. Third_, Nov 05 2026',
                 'a(13)-a(15) from _B. Other_, Nov 05 2026',
                 'More terms from _B. Other_, Nov 05 2026'):
        provenance = {'A217058': [record(13, 14, [58, 61], extensions=line)]}
        _rows, problems = verify_all.others_terms('A217058', 12, provenance, AUTHOR)
        assert any('EXTENSIONS' in p for p in problems), line
