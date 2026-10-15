"""Fixed-geometry invoice renderer.

The invoice is drawn with QPainter in units of 0.1 mm, so every measurement
below is in tenths of a millimetre.  The same function paints the print
preview, the physical printer and the PDF export, so they always match.

All layout constants live in `Layout` - tune them against a test print on the
shop's real stationery (see README, "Calibrating the print").
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QMarginsF, QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QPageLayout, QPageSize,
                           QPainter, QPen, QBrush)
from PySide6.QtPrintSupport import QPrinter

from ..models import BusinessSettings, Invoice
from ..money import format_inr

RED = QColor(139, 26, 26)
INK = QColor(25, 25, 25)
WHITE = QColor(255, 255, 255)
SERIF = ["Times New Roman", "Liberation Serif", "Georgia", "DejaVu Serif", "serif"]


class PrintError(Exception):
    pass


@dataclass(frozen=True)
class Layout:
    """All values in 0.1 mm."""
    contact_h: int = 105
    invoice_banner_w: int = 560
    invoice_banner_h: int = 95
    name_font_px: int = 135
    name_h: int = 150
    category_h: int = 88
    category_font_px: int = 44
    address_font_px: int = 33
    address_line_h: int = 44
    header_gap: int = 28
    field_row_h: int = 105
    field_font_px: int = 40
    left_col_frac: float = 0.56        # width share of left field in 2-up rows
    table_header_h: int = 90
    table_font_px: int = 40
    line_h: int = 62                   # one line of item text
    item_gap: int = 12                 # extra space after each item
    total_h: int = 115
    footer_h: int = 300                # signature block (blank space + labels)
    particulars_frac: float = 0.70
    border_w: int = 4
    cont_header_h: int = 150


L = Layout()


def _font(px: int, bold: bool = False, italic: bool = False) -> QFont:
    f = QFont()
    f.setFamilies(SERIF)
    f.setPixelSize(px)
    f.setBold(bold)
    f.setItalic(italic)
    return f


def configure_printer(printer: QPrinter, s: BusinessSettings) -> None:
    """Apply paper size and margins from settings to a QPrinter."""
    if abs(s.paper_width_mm - 210) < 0.5 and abs(s.paper_height_mm - 297) < 0.5:
        size = QPageSize(QPageSize.PageSizeId.A4)
    else:
        size = QPageSize(QSizeF(s.paper_width_mm, s.paper_height_mm),
                         QPageSize.Unit.Millimeter, "Invoice")
    printer.setPageSize(size)
    printer.setPageOrientation(QPageLayout.Orientation.Portrait)
    layout = printer.pageLayout()
    layout.setUnits(QPageLayout.Unit.Millimeter)
    mn = layout.minimumMargins()  # printer's non-printable area
    m = s.margin_mm
    layout.setMargins(QMarginsF(max(m, mn.left()), max(m, mn.top()),
                                max(m, mn.right()), max(m, mn.bottom())))
    printer.setPageLayout(layout)
    printer.setColorMode(QPrinter.ColorMode.Color)


def _wrap(text: str, fm: QFontMetrics, width: int) -> list[str]:
    """Greedy word wrap; very long words are broken by character."""
    lines: list[str] = []
    for paragraph in text.replace("\r", "").split("\n"):
        words = paragraph.split(" ")
        cur = ""
        for w in words:
            trial = w if not cur else f"{cur} {w}"
            if fm.horizontalAdvance(trial) <= width:
                cur = trial
                continue
            if cur:
                lines.append(cur)
                cur = ""
            while fm.horizontalAdvance(w) > width and len(w) > 1:
                n = len(w)
                while n > 1 and fm.horizontalAdvance(w[:n]) > width:
                    n -= 1
                lines.append(w[:n])
                w = w[n:]
            cur = w
        lines.append(cur)
    return lines or [""]


def _fmt_date(d) -> str:
    return d.strftime("%d/%m/%Y") if d else ""


class _Renderer:
    def __init__(self, painter: QPainter, printer: QPrinter,
                 invoice: Invoice, business: BusinessSettings):
        self.p = painter
        self.inv = invoice
        self.biz = business
        res = printer.resolution()
        self.p.scale(res / 254.0, res / 254.0)  # 1 unit = 0.1 mm
        rect = printer.pageLayout().paintRect(QPageLayout.Unit.Millimeter)
        self.W = int(rect.width() * 10)
        self.H = int(rect.height() * 10)
        self.px = int(self.W * L.particulars_frac)  # particulars column width

    # ---------------------------------------------------------- primitives
    def _fm(self, font: QFont) -> QFontMetrics:
        self.p.setFont(font)
        return self.p.fontMetrics()

    def text(self, x, y, w, h, s, font, color=INK, align=Qt.AlignmentFlag.AlignLeft):
        self.p.setFont(font)
        self.p.setPen(color)
        self.p.drawText(QRectF(x, y, w, h), int(align | Qt.AlignmentFlag.AlignVCenter), s)

    def line(self, x1, y1, x2, y2, width=3, color=RED):
        self.p.setPen(QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        self.p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def banner(self, x, y, w, h, label, px):
        self.p.setPen(Qt.PenStyle.NoPen)
        self.p.setBrush(QBrush(RED))
        self.p.drawRoundedRect(QRectF(x, y, w, h), h / 2.2, h / 2.2)
        self.text(x, y, w, h, label, _font(px, True), WHITE, Qt.AlignmentFlag.AlignHCenter)

    # ------------------------------------------------------------- header
    def full_header(self) -> int:
        b, W = self.biz, self.W
        y = 0
        cf = _font(36, True)
        for x, name, phone, al in (
            (0, b.contact_name_1, b.contact_phone_1, Qt.AlignmentFlag.AlignLeft),
            (W - 600, b.contact_name_2, b.contact_phone_2, Qt.AlignmentFlag.AlignRight),
        ):
            self.text(x, y, 600, L.contact_h / 2, name, cf, INK, al)
            self.text(x, y + L.contact_h / 2, 600, L.contact_h / 2, phone, _font(36), INK, al)
        self.banner((W - L.invoice_banner_w) / 2, y + 8, L.invoice_banner_w,
                    L.invoice_banner_h, "INVOICE", 52)
        y += L.contact_h + 25

        # Business name, shrunk only if it would not fit the page width.
        px = L.name_font_px
        while px > 60 and self._fm(_font(px, True)).horizontalAdvance(b.business_name) > W - 40:
            px -= 4
        self.text(0, y, W, L.name_h, b.business_name, _font(px, True), RED,
                  Qt.AlignmentFlag.AlignHCenter)
        y += L.name_h + 8

        cat_font = _font(L.category_font_px, True)
        cw = min(W, self._fm(cat_font).horizontalAdvance(b.business_category) + 260)
        self.banner((W - cw) / 2, y, cw, L.category_h, b.business_category,
                    L.category_font_px)
        y += L.category_h + 18

        af = _font(L.address_font_px)
        lines = _wrap(b.business_address, self._fm(af), W - 100)
        for ln in lines:
            self.text(0, y, W, L.address_line_h, ln, af, INK, Qt.AlignmentFlag.AlignHCenter)
            y += L.address_line_h
        y += L.header_gap
        self.line(0, y, W, y, 3)
        return y + 20

    def cont_header(self, page: int, pages: int) -> int:
        W = self.W
        self.text(0, 0, W * 0.6, 90, self.biz.business_name, _font(70, True), RED)
        self.text(W * 0.45, 0, W * 0.55, 90,
                  f"INVOICE {self.inv.bill_number}  (continued)  Page {page} of {pages}",
                  _font(36, True), INK, Qt.AlignmentFlag.AlignRight)
        self.line(0, 105, W, 105, 3)
        return L.cont_header_h

    # ------------------------------------------------------ customer block
    def _field(self, x, y, w, label, value):
        lf = _font(L.field_font_px, True)
        lw = self._fm(lf).horizontalAdvance(label) + 25
        self.text(x, y, lw, L.field_row_h, label, lf, INK)
        base = y + L.field_row_h - 12
        self.line(x + lw, base, x + w, base, 2)
        vf = _font(L.field_font_px)
        fm = self._fm(vf)
        value = fm.elidedText(value, Qt.TextElideMode.ElideRight, int(w - lw - 20))
        self.text(x + lw + 10, y, w - lw - 10, L.field_row_h - 6, value, vf, INK)

    def customer_block(self, y: int) -> int:
        W, inv = self.W, self.inv
        gap = 60
        lw = int(W * L.left_col_frac)
        rx = lw + gap
        rh = L.field_row_h
        self._field(0, y, lw, "Bill No.", inv.bill_number)
        self._field(rx, y, W - rx, "Date", _fmt_date(inv.invoice_date))
        y += rh
        self._field(0, y, W, "Customer Name", inv.customer_name)
        y += rh
        self._field(0, y, W, "Customer Address", inv.customer_address)
        y += rh
        self._field(0, y, lw, "Customer Mobile", inv.customer_mobile)
        self._field(rx, y, W - rx, "Date", _fmt_date(inv.additional_date))
        return y + rh + 25

    # --------------------------------------------------------------- table
    def table_header(self, y: int) -> int:
        self.p.setPen(Qt.PenStyle.NoPen)
        self.p.setBrush(QBrush(RED))
        self.p.drawRect(QRectF(0, y, self.W, L.table_header_h))
        hf = _font(L.table_font_px + 4, True)
        self.text(0, y, self.px, L.table_header_h, "Particulars", hf, WHITE,
                  Qt.AlignmentFlag.AlignHCenter)
        self.text(self.px, y, self.W - self.px, L.table_header_h, "Amount", hf, WHITE,
                  Qt.AlignmentFlag.AlignHCenter)
        return y + L.table_header_h

    def table_lines(self):
        """Flatten items into wrapped lines: (text, amount_text|None, ends_item)."""
        tf = _font(L.table_font_px)
        fm = self._fm(tf)
        out = []
        for item in self.inv.items:
            wrapped = _wrap(item.description, fm, self.px - 70)
            for n, ln in enumerate(wrapped):
                out.append((ln, format_inr(item.amount) if n == 0 else None,
                            n == len(wrapped) - 1))
        return out

    def _line_h(self, ends_item: bool) -> int:
        return L.line_h + (L.item_gap if ends_item else 0)

    def paginate(self, lines):
        """Split lines into pages; the last page must also hold total + footer."""
        def top(i):  # body top (below table header) for page i
            return (self._first_body_top if i == 0 else L.cont_header_h + L.table_header_h)

        def cap_mid(i):
            return self.H - 15 - top(i)

        def cap_last(i):
            return self.H - L.footer_h - L.total_h - 25 - top(i)

        pages, cur, used = [], [], 0
        for ln in lines:
            h = self._line_h(ln[2])
            if used + h > cap_mid(len(pages)) and cur:
                pages.append(cur)
                cur, used = [], 0
            cur.append(ln)
            used += h
        if used > cap_last(len(pages)):
            # Keep the last item together with the total rather than orphan it.
            idx = len(cur) - 1
            while idx > 0 and cur[idx][1] is None:
                idx -= 1
            tail = cur[idx:] if idx > 0 else []
            if idx > 0:
                cur = cur[:idx]
            else:
                tail, cur = cur, []
            if cur:
                pages.append(cur)
            cur = tail
        pages.append(cur)
        return pages

    # ----------------------------------------------------------------- run
    def render(self) -> int:
        p = self.p
        # Measure the first-page header height with a dry run (painting to a
        # throwaway state is unnecessary: heights are deterministic).
        self._first_body_top = self._measure_first_top()
        pages = self.paginate(self.table_lines())
        n = len(pages)
        for i, page_lines in enumerate(pages):
            if i > 0:
                self.newpage()
            last = i == n - 1
            if i == 0:
                y = self.full_header()
                y = self.customer_block(y)
            else:
                y = self.cont_header(i + 1, n)
            self.draw_table_page(y, page_lines, last)
        return n

    def newpage(self):
        # Provided by caller through printer.newPage(); set in paint_invoice.
        self._newpage()

    def _measure_first_top(self) -> int:
        b = self.biz
        y = L.contact_h + 25 + L.name_h + 8 + L.category_h + 18
        af = _font(L.address_font_px)
        y += len(_wrap(b.business_address, self._fm(af), self.W - 100)) * L.address_line_h
        y += L.header_gap + 20
        y += 4 * L.field_row_h + 25
        return y + L.table_header_h

    def draw_table_page(self, top: int, lines, last: bool):
        p = self.p
        body_top = self.table_header(top)
        bottom = (self.H - L.footer_h - 25) if last else self.H - 15
        body_bottom = bottom - (L.total_h if last else 0)
        # Item text
        tf = _font(L.table_font_px)
        y = body_top + 14
        for text, amount, ends in lines:
            self.text(35, y, self.px - 70, L.line_h, text, tf, INK)
            if amount is not None:
                self.text(self.px + 20, y, self.W - self.px - 70, L.line_h, amount, tf, INK,
                          Qt.AlignmentFlag.AlignRight)
            y += self._line_h(ends)
        # Frame
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(RED, L.border_w))
        p.drawRect(QRectF(0, top, self.W, bottom - top))
        self.line(self.px, top, self.px, bottom, L.border_w)
        if last:
            self.line(0, body_bottom, self.W, body_bottom, L.border_w)
            tfb = _font(L.table_font_px + 6, True)
            self.text(0, body_bottom, self.px - 60, L.total_h, "TOTAL", tfb, RED,
                      Qt.AlignmentFlag.AlignRight)
            self.text(self.px + 20, body_bottom, self.W - self.px - 70, L.total_h,
                      format_inr(self.inv.total), tfb, INK, Qt.AlignmentFlag.AlignRight)
            self.footer(bottom + 25)

    def footer(self, y: int):
        W = self.W
        ff = _font(38, True)
        base = self.H - 60
        self.text(0, base, W / 2, 60, "Receiver's Signature", ff, INK)
        self.text(W / 2, base, W / 2, 60, f"For. {self.biz.business_name}", ff, INK,
                  Qt.AlignmentFlag.AlignRight)


def paint_invoice(printer: QPrinter, invoice: Invoice, business: BusinessSettings) -> int:
    """Paint all pages of `invoice` onto `printer`. Returns the page count."""
    painter = QPainter()
    if not painter.begin(printer):
        raise PrintError("Could not start printing. Is the printer available and not in use?")
    try:
        r = _Renderer(painter, printer, invoice, business)

        def newpage():
            if not printer.newPage():
                raise PrintError("The printer rejected the next page.")
            painter.resetTransform()
            painter.scale(printer.resolution() / 254.0, printer.resolution() / 254.0)

        r._newpage = newpage
        return r.render()
    finally:
        painter.end()
