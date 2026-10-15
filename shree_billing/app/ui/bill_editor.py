from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemDelegate, QAbstractItemView, QCheckBox,
                               QDateEdit, QFormLayout, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QMessageBox, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..database import Database, DuplicateBillNumber
from ..models import Invoice, InvoiceItem
from ..money import AmountError, format_inr, parse_amount, sum_amounts
from ..printing import print_service
from ..validation import clean_items, validate_invoice

ERR_BG = QBrush(QColor(255, 205, 205))


class ItemTable(QTableWidget):
    """Two-column table. Enter commits the cell and moves to the next one."""

    def __init__(self):
        super().__init__(0, 2)
        self.setHorizontalHeaderLabels(["Particulars", "Amount (₹)"])
        hh = self.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(1, 160)
        self.setWordWrap(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

    def closeEditor(self, editor, hint):
        if hint == QAbstractItemDelegate.EndEditHint.SubmitModelCache:
            hint = QAbstractItemDelegate.EndEditHint.EditNextItem
        super().closeEditor(editor, hint)


class BillEditor(QWidget):
    saved = Signal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.invoice_id: int | None = None
        self.status = "draft"
        self.snapshot = None
        self.dirty = False
        self._loading = False

        self.bill_no = QLineEdit()
        self.bill_no.setMaxLength(20)
        self.bill_no.setToolTip("Suggested automatically. You can change it; it must be unique.")
        self.bill_no.setStyleSheet("")
        self.bill_no.textChanged.connect(self._mark_dirty)
        self.bill_no.editingFinished.connect(self._check_bill_no)
        self.bill_no.returnPressed.connect(lambda: self.name.setFocus())
        self.date = QDateEdit(calendarPopup=True)
        self.date.setDisplayFormat("dd/MM/yyyy")
        self.name = QLineEdit()
        self.address = QLineEdit()
        self.mobile = QLineEdit()
        self.mobile.setMaxLength(10)
        self.mobile.setPlaceholderText("10-digit mobile")
        self.use_extra = QCheckBox("Additional date")
        self.extra_date = QDateEdit(calendarPopup=True)
        self.extra_date.setDisplayFormat("dd/MM/yyyy")
        self.extra_date.setEnabled(False)
        self.use_extra.toggled.connect(self.extra_date.setEnabled)

        form = QFormLayout()
        top = QHBoxLayout()
        top.addWidget(QLabel("Bill No."))
        top.addWidget(self.bill_no)
        top.addSpacing(20)
        top.addWidget(QLabel("Date"))
        top.addWidget(self.date)
        top.addStretch()
        form.addRow(top)
        form.addRow("Customer Name", self.name)
        form.addRow("Customer Address", self.address)
        mob = QHBoxLayout()
        mob.addWidget(self.mobile)
        mob.addSpacing(20)
        mob.addWidget(self.use_extra)
        mob.addWidget(self.extra_date)
        form.addRow("Customer Mobile", mob)

        for a, b in ((self.name, self.address), (self.address, self.mobile)):
            a.returnPressed.connect(b.setFocus)
        self.mobile.returnPressed.connect(self._focus_table)

        self.table = ItemTable()
        self.table.itemChanged.connect(self._item_changed)
        add = QPushButton("Add Row")
        add.clicked.connect(lambda: self.add_row())
        rem = QPushButton("Remove Row")
        rem.clicked.connect(self.remove_row)
        rows = QHBoxLayout()
        rows.addWidget(add)
        rows.addWidget(rem)
        rows.addStretch()
        self.total_label = QLabel()
        self.total_label.setStyleSheet("font-size:20px;font-weight:bold;color:#8b1a1a;")
        rows.addWidget(QLabel("TOTAL"))
        rows.addWidget(self.total_label)

        self.btn_draft = QPushButton("Save Draft")
        self.btn_save = QPushButton("Save Bill")
        self.btn_preview = QPushButton("Print Preview")
        self.btn_print = QPushButton("Print…")
        self.btn_pdf = QPushButton("Export PDF")
        self.btn_save.setDefault(True)
        self.btn_draft.clicked.connect(lambda: self.save(final=False))
        self.btn_save.clicked.connect(lambda: self.save(final=True))
        self.btn_preview.clicked.connect(self.preview)
        self.btn_print.clicked.connect(self.print_bill)
        self.btn_pdf.clicked.connect(self.export_pdf)
        actions = QHBoxLayout()
        actions.addStretch()
        for b in (self.btn_draft, self.btn_save, self.btn_preview, self.btn_print, self.btn_pdf):
            actions.addWidget(b)

        self.heading = QLabel()
        self.heading.setStyleSheet("font-size:18px;font-weight:bold;color:#8b1a1a;")
        lay = QVBoxLayout(self)
        lay.addWidget(self.heading)
        lay.addLayout(form)
        lay.addWidget(self.table, 1)
        lay.addLayout(rows)
        lay.addLayout(actions)

        for w in (self.name, self.address, self.mobile):
            w.textChanged.connect(self._mark_dirty)
        self.date.dateChanged.connect(self._mark_dirty)
        self.extra_date.dateChanged.connect(self._mark_dirty)
        self.use_extra.toggled.connect(self._mark_dirty)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=lambda: self.save(final=True))
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=lambda: self.add_row(focus=True))
        self.new_bill()

    # ---------------------------------------------------------------- state
    def _mark_dirty(self, *_):
        if not self._loading:
            self.dirty = True

    def _check_bill_no(self) -> bool:
        """Highlight the field and warn if the number is empty or already used."""
        text = self.bill_no.text().strip()
        problem = ""
        if not text:
            problem = "Bill number cannot be empty."
        elif self.db.bill_number_exists(text, exclude_id=self.invoice_id):
            problem = f"Bill number {text} is already used by another bill."
        self.bill_no.setStyleSheet("background:#ffcdcd;" if problem else "")
        self.bill_no.setToolTip(problem or "Suggested automatically. You can change it; it must be unique.")
        return not problem

    def _focus_table(self):
        if self.table.rowCount() == 0:
            self.add_row()
        self.table.setCurrentCell(0, 0)
        self.table.setFocus()
        self.table.editItem(self.table.item(0, 0))

    def new_bill(self):
        self._load(Invoice(self.db.next_bill_number(), date.today()))
        self.name.setFocus()

    def load_invoice(self, inv: Invoice):
        self._load(inv)

    def _load(self, inv: Invoice):
        self._loading = True
        self.invoice_id = inv.id
        self.status = inv.status
        self.snapshot = inv.business_snapshot
        self.bill_no.setText(inv.bill_number)
        self.date.setDate(QDate(inv.invoice_date.year, inv.invoice_date.month, inv.invoice_date.day))
        self.name.setText(inv.customer_name)
        self.address.setText(inv.customer_address)
        self.mobile.setText(inv.customer_mobile)
        ad = inv.additional_date
        self.use_extra.setChecked(ad is not None)
        d = ad or inv.invoice_date
        self.extra_date.setDate(QDate(d.year, d.month, d.day))
        self.table.setRowCount(0)
        for it in inv.items:
            self.add_row(it.description, format_inr(it.amount).replace(",", ""))
        for _ in range(max(0, 3 - len(inv.items))):
            self.add_row()
        self.heading.setText(
            ("Edit Bill " if inv.id else "New Bill ") + inv.bill_number
            + (" (finalised)" if inv.status == "final" else " (draft)" if inv.id else ""))
        self._loading = False
        self.dirty = False
        self.bill_no.setStyleSheet("")
        self._update_total()

    # ---------------------------------------------------------------- table
    def add_row(self, desc: str = "", amount: str = "", focus: bool = False):
        was = self._loading
        self._loading = True
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(desc))
        amt = QTableWidgetItem(amount)
        amt.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(r, 1, amt)
        self._loading = was
        if focus:
            self.table.setCurrentCell(r, 0)
            self.table.editItem(self.table.item(r, 0))

    def remove_row(self):
        r = self.table.currentRow()
        if r < 0:
            return
        self.table.removeRow(r)
        self.dirty = True
        self._update_total()

    def _item_changed(self, item: QTableWidgetItem):
        if self._loading:
            return
        self.dirty = True
        if item.column() == 1:
            bad = False
            txt = item.text().strip()
            if txt:
                try:
                    parse_amount(txt)
                except AmountError:
                    bad = True
            # setBackground emits itemChanged again; guard against recursion.
            self._loading = True
            try:
                item.setBackground(ERR_BG if bad else QBrush())
            finally:
                self._loading = False
        self._update_total()
        last = self.table.rowCount() - 1
        if item.row() == last and item.text().strip():
            self.add_row()

    def _read_items(self) -> tuple[list[InvoiceItem], list[str]]:
        items, errors = [], []
        for r in range(self.table.rowCount()):
            desc = (self.table.item(r, 0).text() if self.table.item(r, 0) else "").strip()
            amt_item = self.table.item(r, 1)
            amt_txt = (amt_item.text() if amt_item else "").strip()
            if not desc and not amt_txt:
                continue
            try:
                amount = parse_amount(amt_txt) if amt_txt else Decimal("0.00")
            except AmountError as exc:
                errors.append(f"Row {r + 1}: {exc}")
                amount = Decimal("0.00")
            items.append(InvoiceItem(desc, amount))
        return items, errors

    def _update_total(self):
        items, _ = self._read_items()
        self.total_label.setText("₹ " + format_inr(sum_amounts(i.amount for i in items)))

    # -------------------------------------------------------------- collect
    def collect(self, final: bool) -> Invoice | None:
        """Build an Invoice from the form, or show problems and return None."""
        items, errors = self._read_items()
        qd = self.date.date()
        extra = self.extra_date.date() if self.use_extra.isChecked() else None
        inv = Invoice(
            bill_number=self.bill_no.text().strip(),
            invoice_date=date(qd.year(), qd.month(), qd.day()),
            customer_name=self.name.text().strip(),
            customer_address=self.address.text().strip(),
            customer_mobile=self.mobile.text().strip(),
            additional_date=date(extra.year(), extra.month(), extra.day()) if extra else None,
            items=items, status="final" if final else "draft",
            id=self.invoice_id, business_snapshot=self.snapshot)
        clean_items(inv)
        errors += validate_invoice(inv, final=final)
        if errors:
            QMessageBox.warning(self, "Please fix these problems",
                                "\n".join(f"• {e}" for e in errors))
            return None
        return inv

    # --------------------------------------------------------------- actions
    def save(self, final: bool) -> Invoice | None:
        if self.status == "final" and not final:
            QMessageBox.information(
                self, "Already finalised",
                "A finalised bill cannot be turned back into a draft. Use Save Bill to keep your changes.")
            return None
        inv = self.collect(final)
        if inv is None:
            return None
        if self.invoice_id is not None and self.dirty and self.status == "final":
            ok = QMessageBox.question(
                self, "Overwrite saved bill?",
                f"Bill {inv.bill_number} is already finalised. Save your changes over it?")
            if ok != QMessageBox.StandardButton.Yes:
                return None
        try:
            saved = self.db.save_invoice(inv)
        except DuplicateBillNumber as exc:
            QMessageBox.critical(self, "Duplicate bill number", str(exc))
            return None
        self._load(saved)
        self.saved.emit()
        return saved

    def _invoice_for_output(self, require_saved: bool) -> Invoice | None:
        if require_saved and (self.dirty or self.invoice_id is None or self.status != "final"):
            return self.save(final=True)
        if require_saved:
            return self.db.get_invoice(self.invoice_id)
        return self.collect(final=True)

    def preview(self):
        inv = self._invoice_for_output(require_saved=False)
        if inv:
            print_service.preview(self, inv, self.db.get_settings())

    def print_bill(self):
        inv = self._invoice_for_output(require_saved=True)
        if inv:
            print_service.print_invoice(self, inv, self.db.get_settings())

    def export_pdf(self):
        inv = self._invoice_for_output(require_saved=True)
        if inv:
            print_service.export_pdf(self, inv, self.db.get_settings())
