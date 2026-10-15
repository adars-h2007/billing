"""Sample development data.  Run:  python -m app.sample_data [--db path]"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from decimal import Decimal

from .database import Database, default_db_path
from .models import Invoice, InvoiceItem


def _items(*pairs):
    return [InvoiceItem(d, Decimal(a)) for d, a in pairs]


def seed(db: Database) -> int:
    today = date.today()
    samples = [
        Invoice(db.next_bill_number(), today, "Ramesh Mobile Care",
                "Main Road, Jaysingpur", "9800011122", today, _items(
                    ("Type-C Fast Charger 25W (box of 10)", "2450.00"),
                    ("Tempered glass, assorted models", "1200.50"),
                    ("Back cover, silicone, assorted", "980.00")), "final"),
        Invoice("0000", today - timedelta(days=3), "Sagar Electronics",
                "Station Road, Ichalkaranji", "9922233344", None, _items(
                    ("Display combo, Redmi Note 9 (OG)", "1850"),
                    ("Battery BN-54 compatible, 5 pcs", "1100")), "final"),
    ]
    samples[1].bill_number = f"{int(samples[0].bill_number) + 1:04d}"
    count = 0
    for inv in samples:
        db.save_invoice(inv)
        count += 1
    # An open draft
    draft = Invoice(db.next_bill_number(), today, "Walk-in customer", "", "", None,
                    _items(("Earphones, wired, 20 pcs", "1600")), "draft")
    db.save_invoice(draft)
    return count + 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(default_db_path()))
    args = ap.parse_args()
    database = Database(args.db)
    print(f"Inserted {seed(database)} sample invoices into {args.db}")
