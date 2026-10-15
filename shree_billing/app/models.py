from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from decimal import Decimal
from typing import Optional

from .money import sum_amounts


@dataclass
class InvoiceItem:
    description: str
    amount: Decimal


@dataclass
class BusinessSettings:
    business_name: str = "Shree Wholesale Mobile"
    business_category: str = "Mobile Accessories & Spare Parts"
    business_address: str = (
        "Shop No. 01, Kolekar Complex, Opp. Virshaiv Bank, Near Shahu Highschool, "
        "Ichalkaranji - 416 115, Dist. Kolhapur."
    )
    contact_name_1: str = "Pritam"
    contact_phone_1: str = "9766805863"
    contact_name_2: str = "Sushant"
    contact_phone_2: str = "9552246188"
    paper_width_mm: float = 210.0
    paper_height_mm: float = 297.0
    margin_mm: float = 8.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "BusinessSettings":
        names = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in data.items() if k in names})


@dataclass
class Invoice:
    bill_number: str
    invoice_date: date
    customer_name: str = ""
    customer_address: str = ""
    customer_mobile: str = ""
    additional_date: Optional[date] = None
    items: list[InvoiceItem] = field(default_factory=list)
    status: str = "draft"  # 'draft' or 'final'
    id: Optional[int] = None
    created_at: str = ""
    updated_at: str = ""
    # Business details frozen when the bill is finalised, so reprints of old
    # bills keep their original header even if settings change later.
    business_snapshot: Optional[dict] = None

    @property
    def total(self):
        return sum_amounts(i.amount for i in self.items)
