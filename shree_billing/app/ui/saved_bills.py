from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..database import Database
from ..money import format_inr
from ..printing import print_service


class SavedBills(QWidget):
    open_requested = Signal(int)

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by bill no., customer, mobile or date (dd/mm/yyyy)…")
        self.search.setClearButtonEnabled(True)
        self._timer = QTimer(self, singleShot=True, interval=250)
        self._timer.timeout.connect(self.refresh)
        self.search.textChanged.connect(lambda _: self._timer.start())

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Bill No.", "Date", "Customer", "Mobile", "Total (₹)", "Status"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(lambda *_: self.open_selected())

        buttons = []
        for label, slot in (("Open / Edit", self.open_selected),
                            ("Print Preview", self.preview_selected),
                            ("Print…", self.print_selected),
                            ("Export PDF", self.pdf_selected),
                            ("Delete", self.delete_selected)):
            b = QPushButton(label)
            b.clicked.connect(slot)
            buttons.append(b)
        row = QHBoxLayout()
        row.addStretch()
        for b in buttons:
            row.addWidget(b)
        self.count = QLabel()
        lay = QVBoxLayout(self)
        title = QLabel("Saved Bills")
        title.setStyleSheet("font-size:18px;font-weight:bold;color:#8b1a1a;")
        lay.addWidget(title)
        lay.addWidget(self.search)
        lay.addWidget(self.table, 1)
        lay.addWidget(self.count)
        lay.addLayout(row)
        self.refresh()

    def refresh(self):
        rows = self.db.search_invoices(self.search.text())
        self.table.setRowCount(len(rows))
        for r, d in enumerate(rows):
            vals = [d["bill_number"], date.fromisoformat(d["invoice_date"]).strftime("%d/%m/%Y"),
                    d["customer_name"], d["customer_mobile"],
                    format_inr(Decimal(d["total_amount"])), d["status"].capitalize()]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(v)
                if c == 4:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if c == 0:
                    item.setData(Qt.ItemDataRole.UserRole, d["id"])
                self.table.setItem(r, c, item)
        self.count.setText(f"{len(rows)} bill(s)")

    def _selected_id(self) -> int | None:
        r = self.table.currentRow()
        if r < 0:
            QMessageBox.information(self, "Select a bill", "Please select a bill first.")
            return None
        return self.table.item(r, 0).data(Qt.ItemDataRole.UserRole)

    def open_selected(self):
        i = self._selected_id()
        if i is not None:
            self.open_requested.emit(i)

    def preview_selected(self):
        i = self._selected_id()
        if i is not None:
            print_service.preview(self, self.db.get_invoice(i), self.db.get_settings())

    def print_selected(self):
        i = self._selected_id()
        if i is not None:
            print_service.print_invoice(self, self.db.get_invoice(i), self.db.get_settings())

    def pdf_selected(self):
        i = self._selected_id()
        if i is not None:
            print_service.export_pdf(self, self.db.get_invoice(i), self.db.get_settings())

    def delete_selected(self):
        i = self._selected_id()
        if i is None:
            return
        inv = self.db.get_invoice(i)
        ok = QMessageBox.warning(
            self, "Delete bill?",
            f"Permanently delete bill {inv.bill_number} for "
            f"'{inv.customer_name or 'unnamed customer'}'?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)
        if ok == QMessageBox.StandardButton.Yes:
            self.db.delete_invoice(i)
            self.refresh()
