from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QLineEdit, QMessageBox,
                               QPlainTextEdit, QPushButton, QVBoxLayout)

from ..database import Database
from ..models import BusinessSettings

PRESETS = {"A4 (210 × 297 mm)": (210.0, 297.0), "A5 (148 × 210 mm)": (148.0, 210.0),
           "Custom (set below)": None}


class SettingsDialog(QDialog):
    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Business Settings")
        self.resize(560, 560)
        s = db.get_settings()
        self.name = QLineEdit(s.business_name)
        self.category = QLineEdit(s.business_category)
        self.address = QPlainTextEdit(s.business_address)
        self.address.setFixedHeight(70)
        self.c1n, self.c1p = QLineEdit(s.contact_name_1), QLineEdit(s.contact_phone_1)
        self.c2n, self.c2p = QLineEdit(s.contact_name_2), QLineEdit(s.contact_phone_2)
        self.preset = QComboBox()
        self.preset.addItems(PRESETS)
        self.w = QDoubleSpinBox(minimum=80, maximum=500, decimals=1, suffix=" mm", value=s.paper_width_mm)
        self.h = QDoubleSpinBox(minimum=80, maximum=700, decimals=1, suffix=" mm", value=s.paper_height_mm)
        self.margin = QDoubleSpinBox(minimum=0, maximum=40, decimals=1, suffix=" mm", value=s.margin_mm)
        self._sync_preset()
        self.preset.currentTextChanged.connect(self._preset_changed)

        form = QFormLayout()
        form.addRow("Business name", self.name)
        form.addRow("Category", self.category)
        form.addRow("Address", self.address)
        form.addRow("Contact 1 name", self.c1n)
        form.addRow("Contact 1 phone", self.c1p)
        form.addRow("Contact 2 name", self.c2n)
        form.addRow("Contact 2 phone", self.c2p)
        form.addRow("Paper size", self.preset)
        form.addRow("Paper width", self.w)
        form.addRow("Paper height", self.h)
        form.addRow("Page margin", self.margin)

        backup = QPushButton("Back up database…")
        backup.clicked.connect(self._backup)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(backup)
        lay.addWidget(buttons)

    def _sync_preset(self):
        for label, size in PRESETS.items():
            if size and (self.w.value(), self.h.value()) == size:
                self.preset.setCurrentText(label)
                return
        self.preset.setCurrentText("Custom (set below)")

    def _preset_changed(self, label):
        size = PRESETS.get(label)
        if size:
            self.w.setValue(size[0])
            self.h.setValue(size[1])

    def _backup(self):
        default = f"billing-backup-{datetime.now():%Y%m%d-%H%M}.db"
        path, _ = QFileDialog.getSaveFileName(self, "Back up database", default, "SQLite (*.db)")
        if path:
            try:
                self.db.backup_to(path)
                QMessageBox.information(self, "Backup complete", f"Saved to:\n{path}")
            except Exception as exc:  # noqa: BLE001 - show any I/O failure to the user
                QMessageBox.critical(self, "Backup failed", str(exc))

    def _save(self):
        if not self.name.text().strip():
            QMessageBox.warning(self, "Missing name", "Business name cannot be empty.")
            return
        self.db.save_settings(BusinessSettings(
            self.name.text().strip(), self.category.text().strip(),
            self.address.toPlainText().strip(),
            self.c1n.text().strip(), self.c1p.text().strip(),
            self.c2n.text().strip(), self.c2p.text().strip(),
            self.w.value(), self.h.value(), self.margin.value()))
        self.accept()
