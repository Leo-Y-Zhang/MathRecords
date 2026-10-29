import pytest

from verify_certificate import find_ap, verify


def test_one_changed_colour_creates_an_ap():
    assert verify('1122', 0, [3, 4]) == ([], 0)
    problems, dots = verify('1112', 0, [3, 4])
    assert dots == 0
    assert any('colour 1 contains' in problem for problem in problems)


def test_wildcard_budget_includes_the_limit():
    assert verify('.11', 1, [3]) == ([], 1)
    problems, dots = verify('..1', 1, [3])
    assert dots == 2
    assert any('wildcards' in problem for problem in problems)


@pytest.mark.parametrize('symbol', ['0', '3', 'x', '\n'])
def test_unknown_symbols_are_rejected(symbol):
    problems, _ = verify('112' + symbol, 0, [3, 4])
    assert any('unexpected symbols' in problem for problem in problems)


def test_ap_search_checks_later_starts_and_the_right_endpoint():
    assert find_ap([1, 2, 6, 10], 3, 10) == (2, 4)
    assert find_ap([1, 3, 5], 3, 5) == (1, 2)
    assert find_ap([1, 3], 3, 5) is None
    assert find_ap([1, 3, 5], 4, 5) is None


def test_each_colour_uses_its_own_target():
    assert verify('222', 0, [3, 4]) == ([], 0)
    problems, _ = verify('2222', 0, [3, 4])
    assert any('colour 2 contains the 4-term AP' in p for p in problems)
