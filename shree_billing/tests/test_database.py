from datetime import date
from decimal import Decimal

import pytest

from app.database import Database, DuplicateBillNumber, InvoiceNotFound
from app.models import BusinessSettings, Invoice, InvoiceItem
from app.validation import clean_items, validate_invoice


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "t.db")
    yield d
    d.close()


def make(db, **kw):
    base = dict(bill_number=db.next_bill_number(), invoice_date=date(2026, 10, 14),
                customer_name="Ramesh", customer_address="Main Rd", customer_mobile="9800011122",
                items=[InvoiceItem("Charger", Decimal("100.10")),
                       InvoiceItem("Cable", Decimal("50.20")),
                       InvoiceItem("Glass", Decimal("0.70"))], status="final")
    base.update(kw)
    return Invoice(**base)


def test_total_is_sum_of_items(db):
    assert make(db).total == Decimal("151.00")


def test_save_and_reopen_roundtrip(db):
    saved = db.save_invoice(make(db, additional_date=date(2026, 10, 1)))
    again = db.get_invoice(saved.id)
    assert again.customer_name == "Ramesh"
    assert again.additional_date == date(2026, 10, 1)
    assert [(i.description, i.amount) for i in again.items] == [
        ("Charger", Decimal("100.10")), ("Cable", Decimal("50.20")), ("Glass", Decimal("0.70"))]
    assert again.total == Decimal("151.00")


def test_bill_numbers_increment_and_are_unique(db):
    a = db.save_invoice(make(db))
    assert db.next_bill_number() == "0002"
    with pytest.raises(DuplicateBillNumber):
        db.save_invoice(make(db, bill_number=a.bill_number))


def test_failed_save_leaves_no_partial_data(db):
    db.save_invoice(make(db))
    with pytest.raises(DuplicateBillNumber):
        db.save_invoice(make(db, bill_number="0001"))
    assert db.conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0] == 1
    assert db.conn.execute("SELECT COUNT(*) FROM invoice_items").fetchone()[0] == 3


def test_update_replaces_items(db):
    saved = db.save_invoice(make(db))
    saved.items = [InvoiceItem("Only item", Decimal("5"))]
    db.save_invoice(saved)
    assert len(db.get_invoice(saved.id).items) == 1
    assert db.conn.execute("SELECT COUNT(*) FROM invoice_items").fetchone()[0] == 1


def test_delete_cascades_items(db):
    saved = db.save_invoice(make(db))
    db.delete_invoice(saved.id)
    assert db.conn.execute("SELECT COUNT(*) FROM invoice_items").fetchone()[0] == 0
    with pytest.raises(InvoiceNotFound):
        db.get_invoice(saved.id)


def test_search_by_all_fields(db):
    db.save_invoice(make(db))
    for q in ("0001", "ramesh", "98000", "14/10/2026", "2026-10-14"):
        assert len(db.search_invoices(q)) == 1, q
    assert db.search_invoices("nobody") == []


def test_reprint_uses_original_business_snapshot(db):
    saved = db.save_invoice(make(db))
    s = db.get_settings()
    s.business_name = "Renamed Shop"
    db.save_settings(s)
    again = db.get_invoice(saved.id)
    assert again.business_snapshot["business_name"] == "Shree Wholesale Mobile"


def test_settings_default_and_update(db):
    s = db.get_settings()
    assert s.contact_phone_1 == "9766805863" and s.contact_name_2 == "Sushant"
    s.margin_mm = 12.5
    db.save_settings(s)
    assert db.get_settings().margin_mm == 12.5


def test_backup_is_restorable(db, tmp_path):
    db.save_invoice(make(db))
    db.backup_to(tmp_path / "b.db")
    copy = Database(tmp_path / "b.db")
    assert len(copy.search_invoices()) == 1
    copy.close()


def test_validation_rules(db):
    inv = make(db, customer_name="", customer_mobile="123")
    errs = validate_invoice(inv, final=True)
    assert any("name" in e for e in errs) and any("10 digits" in e for e in errs)
    empty = make(db, items=[])
    assert any("at least one" in e for e in validate_invoice(empty, final=True))
    assert not any("at least one" in e for e in validate_invoice(empty, final=False))
    blank = make(db, items=[InvoiceItem("", Decimal("0")), InvoiceItem("X", Decimal("3"))])
    clean_items(blank)
    assert len(blank.items) == 1
