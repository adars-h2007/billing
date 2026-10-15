"""SQLite persistence. No UI or printing code lives here."""
from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

from .models import BusinessSettings, Invoice, InvoiceItem
from .money import parse_amount

SCHEMA = """
CREATE TABLE IF NOT EXISTS invoices (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_number       TEXT NOT NULL UNIQUE,
    invoice_date      TEXT NOT NULL,
    customer_name     TEXT NOT NULL DEFAULT '',
    customer_address  TEXT NOT NULL DEFAULT '',
    customer_mobile   TEXT NOT NULL DEFAULT '',
    additional_date   TEXT,
    total_amount      TEXT NOT NULL DEFAULT '0.00',
    status            TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','final')),
    business_snapshot TEXT,
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now','localtime')),
    updated_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now','localtime'))
);

CREATE TABLE IF NOT EXISTS invoice_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id    INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    description   TEXT NOT NULL,
    amount        TEXT NOT NULL,
    display_order INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_invoice ON invoice_items(invoice_id, display_order);
CREATE INDEX IF NOT EXISTS idx_invoices_customer ON invoices(customer_name);
CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices(invoice_date);

CREATE TABLE IF NOT EXISTS business_settings (
    id               INTEGER PRIMARY KEY CHECK (id = 1),
    business_name    TEXT NOT NULL,
    business_category TEXT NOT NULL,
    business_address TEXT NOT NULL,
    contact_name_1   TEXT NOT NULL,
    contact_phone_1  TEXT NOT NULL,
    contact_name_2   TEXT NOT NULL,
    contact_phone_2  TEXT NOT NULL,
    paper_width_mm   REAL NOT NULL DEFAULT 210,
    paper_height_mm  REAL NOT NULL DEFAULT 297,
    margin_mm        REAL NOT NULL DEFAULT 8
);
"""


class DuplicateBillNumber(Exception):
    """A different invoice already uses this bill number."""


class InvoiceNotFound(Exception):
    pass


def default_db_path() -> Path:
    env = os.environ.get("SHREE_BILLING_DB")
    if env:
        return Path(env)
    return Path.home() / "ShreeBilling" / "billing.db"


def _d(value: Optional[date]) -> Optional[str]:
    return value.isoformat() if value else None


def _parse_date(text: Optional[str]) -> Optional[date]:
    return date.fromisoformat(text) if text else None


class Database:
    def __init__(self, path: Path | str = ":memory:"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.initialize()

    # ------------------------------------------------------------ setup
    def initialize(self) -> None:
        with self.conn:
            self.conn.executescript(SCHEMA)
            row = self.conn.execute("SELECT 1 FROM business_settings WHERE id=1").fetchone()
            if row is None:
                self._write_settings(BusinessSettings())

    def close(self) -> None:
        self.conn.close()

    def backup_to(self, destination: Path | str) -> None:
        """Consistent online backup using SQLite's backup API."""
        dest = sqlite3.connect(str(destination))
        try:
            with dest:
                self.conn.backup(dest)
        finally:
            dest.close()

    # --------------------------------------------------------- settings
    def _write_settings(self, s: BusinessSettings) -> None:
        self.conn.execute(
            """INSERT INTO business_settings
               (id, business_name, business_category, business_address,
                contact_name_1, contact_phone_1, contact_name_2, contact_phone_2,
                paper_width_mm, paper_height_mm, margin_mm)
               VALUES (1,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                business_name=excluded.business_name,
                business_category=excluded.business_category,
                business_address=excluded.business_address,
                contact_name_1=excluded.contact_name_1,
                contact_phone_1=excluded.contact_phone_1,
                contact_name_2=excluded.contact_name_2,
                contact_phone_2=excluded.contact_phone_2,
                paper_width_mm=excluded.paper_width_mm,
                paper_height_mm=excluded.paper_height_mm,
                margin_mm=excluded.margin_mm""",
            (s.business_name, s.business_category, s.business_address,
             s.contact_name_1, s.contact_phone_1, s.contact_name_2, s.contact_phone_2,
             s.paper_width_mm, s.paper_height_mm, s.margin_mm),
        )

    def get_settings(self) -> BusinessSettings:
        row = self.conn.execute("SELECT * FROM business_settings WHERE id=1").fetchone()
        data = dict(row)
        data.pop("id")
        return BusinessSettings.from_dict(data)

    def save_settings(self, settings: BusinessSettings) -> None:
        with self.conn:
            self._write_settings(settings)

    # ----------------------------------------------------- bill numbers
    def next_bill_number(self) -> str:
        row = self.conn.execute(
            "SELECT MAX(CAST(bill_number AS INTEGER)) FROM invoices "
            "WHERE bill_number NOT GLOB '*[^0-9]*'"
        ).fetchone()
        return f"{(row[0] or 0) + 1:04d}"

    def bill_number_exists(self, bill_number: str, exclude_id: Optional[int] = None) -> bool:
        row = self.conn.execute(
            "SELECT id FROM invoices WHERE bill_number=?", (bill_number,)
        ).fetchone()
        return row is not None and row["id"] != exclude_id

    # ---------------------------------------------------------- saving
    def save_invoice(self, inv: Invoice) -> Invoice:
        """Insert or update an invoice and its items in one transaction."""
        if self.bill_number_exists(inv.bill_number, exclude_id=inv.id):
            raise DuplicateBillNumber(
                f"Bill number {inv.bill_number} is already used by another invoice."
            )
        snapshot = (
            json.dumps(inv.business_snapshot) if inv.business_snapshot else None
        )
        if inv.status == "final" and snapshot is None:
            snapshot = json.dumps(self.get_settings().to_dict())
            inv.business_snapshot = json.loads(snapshot)
        total = str(inv.total)
        try:
            with self.conn:  # commits on success, rolls back on any exception
                if inv.id is None:
                    cur = self.conn.execute(
                        """INSERT INTO invoices
                           (bill_number, invoice_date, customer_name, customer_address,
                            customer_mobile, additional_date, total_amount, status,
                            business_snapshot)
                           VALUES (?,?,?,?,?,?,?,?,?)""",
                        (inv.bill_number, inv.invoice_date.isoformat(), inv.customer_name,
                         inv.customer_address, inv.customer_mobile,
                         _d(inv.additional_date), total, inv.status, snapshot),
                    )
                    inv.id = cur.lastrowid
                else:
                    cur = self.conn.execute(
                        """UPDATE invoices SET bill_number=?, invoice_date=?, customer_name=?,
                           customer_address=?, customer_mobile=?, additional_date=?,
                           total_amount=?, status=?, business_snapshot=?,
                           updated_at=strftime('%Y-%m-%d %H:%M:%S','now','localtime')
                           WHERE id=?""",
                        (inv.bill_number, inv.invoice_date.isoformat(), inv.customer_name,
                         inv.customer_address, inv.customer_mobile,
                         _d(inv.additional_date), total, inv.status, snapshot, inv.id),
                    )
                    if cur.rowcount == 0:
                        raise InvoiceNotFound(f"Invoice id {inv.id} no longer exists.")
                    self.conn.execute("DELETE FROM invoice_items WHERE invoice_id=?", (inv.id,))
                self.conn.executemany(
                    "INSERT INTO invoice_items (invoice_id, description, amount, display_order) "
                    "VALUES (?,?,?,?)",
                    [(inv.id, i.description, str(i.amount), n)
                     for n, i in enumerate(inv.items)],
                )
        except sqlite3.IntegrityError as exc:
            if "bill_number" in str(exc):
                raise DuplicateBillNumber(
                    f"Bill number {inv.bill_number} is already used."
                ) from exc
            raise
        return self.get_invoice(inv.id)

    # --------------------------------------------------------- reading
    def _row_to_invoice(self, row: sqlite3.Row) -> Invoice:
        items = [
            InvoiceItem(r["description"], parse_amount(Decimal(r["amount"])))
            for r in self.conn.execute(
                "SELECT description, amount FROM invoice_items "
                "WHERE invoice_id=? ORDER BY display_order", (row["id"],))
        ]
        snap = json.loads(row["business_snapshot"]) if row["business_snapshot"] else None
        return Invoice(
            id=row["id"], bill_number=row["bill_number"],
            invoice_date=date.fromisoformat(row["invoice_date"]),
            customer_name=row["customer_name"], customer_address=row["customer_address"],
            customer_mobile=row["customer_mobile"],
            additional_date=_parse_date(row["additional_date"]),
            items=items, status=row["status"],
            created_at=row["created_at"], updated_at=row["updated_at"],
            business_snapshot=snap,
        )

    def get_invoice(self, invoice_id: int) -> Invoice:
        row = self.conn.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if row is None:
            raise InvoiceNotFound(f"Invoice id {invoice_id} not found.")
        return self._row_to_invoice(row)

    def search_invoices(self, text: str = "", limit: int = 500) -> list[dict]:
        """Search by bill number, customer name, mobile or date (dd/mm/yyyy or yyyy-mm-dd)."""
        text = text.strip()
        sql = ("SELECT id, bill_number, invoice_date, customer_name, customer_mobile, "
               "total_amount, status FROM invoices")
        params: list = []
        if text:
            like = f"%{text}%"
            iso = text
            m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", text)
            if m:
                iso = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
            sql += (" WHERE bill_number LIKE ? OR customer_name LIKE ? "
                    "OR customer_mobile LIKE ? OR invoice_date LIKE ?")
            params = [like, like, like, f"%{iso}%"]
        sql += " ORDER BY invoice_date DESC, id DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self.conn.execute(sql, params)]

    def delete_invoice(self, invoice_id: int) -> None:
        with self.conn:
            cur = self.conn.execute("DELETE FROM invoices WHERE id=?", (invoice_id,))
            if cur.rowcount == 0:
                raise InvoiceNotFound(f"Invoice id {invoice_id} not found.")
