from decimal import Decimal

from app.database import Database
from app.ui.main_window import MainWindow


def test_editor_end_to_end(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.Ok)
    db = Database(tmp_path / "ui.db")
    win = MainWindow(db)
    ed = win.editor

    # Three line items, total updates automatically
    ed.name.setText("Test Customer")
    ed.mobile.setText("9800011122")
    for r, (d, a) in enumerate([("Charger", "100.10"), ("Cable", "50.20"), ("Glass", "0.70")]):
        ed.table.item(r, 0).setText(d)
        ed.table.item(r, 1).setText(a)
    assert "151.00" in ed.total_label.text()

    # Invalid amount blocks saving
    ed.table.item(0, 1).setText("abc")
    assert ed.save(final=True) is None
    ed.table.item(0, 1).setText("100.10")

    saved = ed.save(final=True)
    assert saved is not None and saved.total == Decimal("151.00")

    # Reopen from the database
    ed.new_bill()
    assert ed.bill_no.text() == "0002"
    ed.load_invoice(db.get_invoice(saved.id))
    assert ed.name.text() == "Test Customer"
    assert ed.table.item(1, 0).text() == "Cable"
    db.close()


def test_bill_number_is_editable_and_unique(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: shown.append(a[2]))
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.Ok)
    db = Database(tmp_path / "bn.db")
    win = MainWindow(db)
    ed = win.editor
    assert not ed.bill_no.isReadOnly()

    def fill(number):
        ed.bill_no.setText(number)
        ed.name.setText("Cust")
        ed.table.item(0, 0).setText("Item")
        ed.table.item(0, 1).setText("10")

    fill("A-101")
    saved = ed.save(final=True)
    assert saved is not None and saved.bill_number == "A-101"

    ed.new_bill()
    assert ed.bill_no.text() == "0001"           # numeric suggestion ignores 'A-101'
    fill("A-101")                                  # duplicate
    assert ed._check_bill_no() is False
    assert ed.save(final=True) is None and shown  # blocked with an error dialog
    fill("A-102")
    assert ed._check_bill_no() is True
    assert ed.save(final=True).bill_number == "A-102"
    db.close()
