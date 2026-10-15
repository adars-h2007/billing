"""Monetary helpers. All money is handled as Decimal with 2 places."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

TWO_PLACES = Decimal("0.01")
MAX_AMOUNT = Decimal("999999999.99")


class AmountError(ValueError):
    """Raised when an amount string is not a valid, non-negative amount."""


def quantize(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def parse_amount(text: str | Decimal | int | float | None) -> Decimal:
    """Parse user input such as '1,250.5', '₹ 99' or 'Rs. 10' into a Decimal.

    Negative, non-numeric, non-finite and absurdly large values are rejected.
    """
    if text is None:
        raise AmountError("Amount is empty.")
    if isinstance(text, Decimal):
        value = text
    else:
        cleaned = str(text).strip()
        for token in ("₹", "Rs.", "Rs", "INR", ",", " "):
            cleaned = cleaned.replace(token, "")
        if not cleaned:
            raise AmountError("Amount is empty.")
        try:
            value = Decimal(cleaned)
        except InvalidOperation:
            raise AmountError(f"'{text}' is not a valid amount.") from None
    if not value.is_finite():
        raise AmountError("Amount must be a finite number.")
    if value < 0:
        raise AmountError("Amount cannot be negative.")
    if value > MAX_AMOUNT:  # check before rounding: huge values overflow quantize()
        raise AmountError("Amount is too large.")
    return quantize(value)


def format_inr(value: Decimal | int | str, symbol: bool = False) -> str:
    """Format using Indian digit grouping: 1234567.5 -> 12,34,567.50"""
    q = quantize(Decimal(value))
    sign = "-" if q < 0 else ""
    integer, _, frac = f"{abs(q):.2f}".partition(".")
    if len(integer) > 3:
        head, tail = integer[:-3], integer[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        integer = ",".join(groups + [tail])
    return f"{'₹ ' if symbol else ''}{sign}{integer}.{frac}"


def sum_amounts(values) -> Decimal:
    total = Decimal("0.00")
    for v in values:
        total += v
    return quantize(total)
