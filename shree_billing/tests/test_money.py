from decimal import Decimal

import pytest

from app.money import AmountError, format_inr, parse_amount, sum_amounts


def test_parse_variants():
    assert parse_amount("1,250.5") == Decimal("1250.50")
    assert parse_amount("₹ 99") == Decimal("99.00")
    assert parse_amount("Rs. 10") == Decimal("10.00")


@pytest.mark.parametrize("bad", ["", "abc", "-5", "NaN", "Infinity", "1e30", None])
def test_parse_rejects(bad):
    with pytest.raises(AmountError):
        parse_amount(bad)


def test_decimal_exactness():
    # 0.1 + 0.2 must be exactly 0.30 (floats would give 0.30000000000000004)
    assert sum_amounts([Decimal("0.10"), Decimal("0.20")]) == Decimal("0.30")


def test_rounding_half_up():
    assert parse_amount("2.675") == Decimal("2.68")


@pytest.mark.parametrize("value,expected", [
    ("0", "0.00"), ("999", "999.00"), ("1000", "1,000.00"),
    ("123456", "1,23,456.00"), ("1234567.5", "12,34,567.50"),
])
def test_indian_grouping(value, expected):
    assert format_inr(Decimal(value)) == expected
