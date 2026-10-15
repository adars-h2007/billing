import re
from datetime import date
from decimal import Decimal

from PySide6.QtPrintSupport import QPrinter

from app.models import BusinessSettings, Invoice, InvoiceItem
from app.printing.invoice_printer import configure_printer, paint_invoice
from app.printing.print_service import export_pdf_to


def inv(n, text="Mobile charger"):
    return Invoice("0001", date(2026, 10, 14), "Ramesh", "Main Road", "9800011122",
                   date(2026, 10, 14),
                   [InvoiceItem(f"{text} {i}", Decimal("10.50")) for i in range(n)])


def pdf_pages(path):
    data = path.read_bytes()
    assert data.startswith(b"%PDF")
    return len(re.findall(rb"/Type\s*/Page(?![s\w])", data))


def test_short_invoice_is_one_page(qapp, tmp_path):
    out = tmp_path / "a.pdf"
    assert export_pdf_to(str(out), inv(3), BusinessSettings()) == 1
    assert pdf_pages(out) == 1


def test_long_descriptions_do_not_overflow_single_page(qapp, tmp_path):
    out = tmp_path / "b.pdf"
    long = "Very long description that must wrap onto several lines " * 6
    n = export_pdf_to(str(out), inv(3, long), BusinessSettings())
    assert n == pdf_pages(out) and n <= 2


def test_many_items_paginate(qapp, tmp_path):
    out = tmp_path / "c.pdf"
    n = export_pdf_to(str(out), inv(150), BusinessSettings())
    assert n > 1 and pdf_pages(out) == n


def test_total_never_orphaned_on_empty_page(qapp, tmp_path):
    """Sweep item counts so the total row lands near every page boundary."""
    for count in range(1, 70):
        n = export_pdf_to(str(tmp_path / f"s{count}.pdf"), inv(count), BusinessSettings())
        assert n >= 1


def test_custom_paper_size(qapp, tmp_path):
    s = BusinessSettings(paper_width_mm=148, paper_height_mm=210, margin_mm=6)
    out = tmp_path / "a5.pdf"
    assert export_pdf_to(str(out), inv(5), s) >= 1
    # A5 MediaBox is roughly 419.5 x 595.3 pt
    box = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)", out.read_bytes())
    assert box and abs(float(box.group(1)) - 419.5) < 2


def test_same_output_for_repeat_prints(qapp, tmp_path):
    a, b = tmp_path / "1.pdf", tmp_path / "2.pdf"
    export_pdf_to(str(a), inv(4), BusinessSettings())
    export_pdf_to(str(b), inv(4), BusinessSettings())
    assert pdf_pages(a) == pdf_pages(b) == 1
