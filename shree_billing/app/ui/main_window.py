from __future__ import annotations

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from ..database import Database
from .bill_editor import BillEditor
from .saved_bills import SavedBills
from .settings_dialog import SettingsDialog

STYLE = """
QMainWindow, QWidget#content { background: #fbf7f5; }
QWidget#sidebar { background: #8b1a1a; }
QWidget#sidebar QPushButton { color: white; background: transparent; border: none;
    text-align: left; padding: 12px 18px; font-size: 14px; }
QWidget#sidebar QPushButton:hover { background: #a52a2a; }
QWidget#sidebar QLabel { color: white; font-size: 16px; font-weight: bold; padding: 16px 18px; }
QPushButton { padding: 6px 14px; }
"""


class MainWindow(QMainWindow):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.setWindowTitle("Shree Wholesale Mobile — Billing")
        self.resize(1100, 760)
        self.setStyleSheet(STYLE)

        self.editor = BillEditor(db)
        self.saved = SavedBills(db)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.editor)
        self.stack.addWidget(self.saved)

        side = QWidget(objectName="sidebar")
        side.setFixedWidth(200)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)
        sl.addWidget(QLabel("Shree Wholesale\nMobile"))
        for label, slot in (("＋  New Bill", self.new_bill),
                            ("☰  Saved Bills", self.show_saved),
                            ("⎙  Print Preview", self.editor.preview),
                            ("⚙  Business Settings", self.open_settings),
                            ("✕  Exit", self.close)):
            b = QPushButton(label)
            b.clicked.connect(slot)
            sl.addWidget(b)
        sl.addStretch()

        content = QWidget(objectName="content")
        cl = QVBoxLayout(content)
        cl.addWidget(self.stack)
        root = QWidget()
        rl = QHBoxLayout(root)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        rl.addWidget(side)
        rl.addWidget(content, 1)
        self.setCentralWidget(root)

        self.saved.open_requested.connect(self.open_bill)
        self.editor.saved.connect(self.saved.refresh)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.new_bill)
        QShortcut(QKeySequence("Ctrl+P"), self, activated=self.editor.preview)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.show_saved)

    def _confirm_discard(self) -> bool:
        if self.stack.currentWidget() is self.editor and self.editor.dirty:
            r = QMessageBox.question(
                self, "Unsaved changes",
                "The bill on screen has unsaved changes. Discard them?")
            return r == QMessageBox.StandardButton.Yes
        return True

    def new_bill(self):
        if self._confirm_discard():
            self.editor.new_bill()
            self.stack.setCurrentWidget(self.editor)

    def show_saved(self):
        self.saved.refresh()
        self.stack.setCurrentWidget(self.saved)
        self.saved.search.setFocus()

    def open_bill(self, invoice_id: int):
        if not self._confirm_discard():
            return
        inv = self.db.get_invoice(invoice_id)
        if inv.status == "final":
            r = QMessageBox.question(
                self, "Edit finalised bill?",
                f"Bill {inv.bill_number} is already finalised.\n\n"
                "You can edit it, but saving will replace the stored copy. Continue?")
            if r != QMessageBox.StandardButton.Yes:
                return
        self.editor.load_invoice(inv)
        self.stack.setCurrentWidget(self.editor)

    def open_settings(self):
        SettingsDialog(self.db, self).exec()

    def closeEvent(self, event):
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()
