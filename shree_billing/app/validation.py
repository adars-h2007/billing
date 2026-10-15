"""Business-rule validation, independent of UI and database."""
from __future__ import annotations

import re

from .models import Invoice

MOBILE_RE = re.compile(r"^\d{10}$")


def clean_items(invoice: Invoice) -> None:
    """Drop rows that are completely empty (no text and zero amount)."""
    invoice.items = [
        i for i in invoice.items if i.description.strip() or i.amount > 0
    ]
    for item in invoice.items:
        item.description = item.description.strip()


def validate_invoice(invoice: Invoice, final: bool) -> list[str]:
    """Return a list of human-readable problems (empty list means valid)."""
    errors: list[str] = []
    if not invoice.bill_number.strip():
        errors.append("Bill number is missing.")
    if invoice.invoice_date is None:
        errors.append("Invoice date is required.")
    mobile = invoice.customer_mobile.strip()
    if mobile and not MOBILE_RE.match(mobile):
        errors.append("Customer mobile must be exactly 10 digits.")
    for n, item in enumerate(invoice.items, start=1):
        if item.amount < 0:
            errors.append(f"Row {n}: amount cannot be negative.")
        if item.amount > 0 and not item.description.strip():
            errors.append(f"Row {n}: description is missing.")
        if item.description.strip() and item.amount <= 0:
            errors.append(f"Row {n}: amount must be greater than zero.")
    if final:
        if not invoice.customer_name.strip():
            errors.append("Customer name is required.")
        if not invoice.items:
            errors.append("Add at least one item with an amount.")
    return errors
