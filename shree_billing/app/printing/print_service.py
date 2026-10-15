"""Preview / print / PDF-export entry points used by the UI."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtPrintSupport import (QPrintDialog, QPrintPreviewDialog, QPrinter,
                                    QPrinterInfo)
from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from ..models import BusinessSettings, Invoice
from .invoice_printer import PrintError, configure_printer, paint_invoice


def _business_for(invoice: Invoice, current: BusinessSettings) -> BusinessSettings:
    """Finalised bills reprint with the business details they were issued with,
    but always use the *current* paper size and margins (stationery may change)."""
    if invoice.business_snapshot:
        merged = BusinessSettings.from_dict(invoice.business_snapshot)
        merged.paper_width_mm = current.paper_width_mm
        merged.paper_height_mm = current.paper_height_mm
        merged.margin_mm = current.margin_mm
        return merged
    return current


def _new_printer(business: BusinessSettings) -> QPrinter:
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    configure_printer(printer, business)
    return printer


def preview(parent: QWidget, invoice: Invoice, current: BusinessSettings) -> None:
    biz = _business_for(invoice, current)
    printer = _new_printer(biz)
    dlg = QPrintPreviewDialog(printer, parent)
    dlg.setWindowTitle(f"Print Preview - Bill {invoice.bill_number}")
    dlg.resize(900, 760)

    def draw(p: QPrinter):
        try:
            paint_invoice(p, invoice, biz)
        except PrintError as exc:
            QMessageBox.critical(parent, "Print error", str(exc))

    dlg.paintRequested.connect(draw)
    dlg.exec()


def print_invoice(parent: QWidget, invoice: Invoice, current: BusinessSettings) -> bool:
    """Show the printer dialog (with copies) and print. Returns True if printed."""
    if not QPrinterInfo.availablePrinters():
        choice = QMessageBox.question(
            parent, "No printer found",
            "No printer is installed or available on this computer.\n\n"
            "Would you like to save the invoice as a PDF instead?")
        if choice == QMessageBox.StandardButton.Yes:
            return export_pdf(parent, invoice, current)
        return False
    biz = _business_for(invoice, current)
    printer = _new_printer(biz)
    dlg = QPrintDialog(printer, parent)
    dlg.setWindowTitle("Print Invoice")
    if dlg.exec() != QPrintDialog.DialogCode.Accepted:
        return False  # user cancelled - not an error
    try:
        paint_invoice(printer, invoice, biz)
    except PrintError as exc:
        QMessageBox.critical(parent, "Print error", str(exc))
        return False
    if printer.printerState() == QPrinter.PrinterState.Error:
        QMessageBox.warning(parent, "Printer error",
                            "The printer reported an error. Check paper, ink and connection.")
        return False
    return True


def export_pdf_to(path: str, invoice: Invoice, current: BusinessSettings) -> int:
    biz = _business_for(invoice, current)
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(path)
    configure_printer(printer, biz)
    return paint_invoice(printer, invoice, biz)


def export_pdf(parent: QWidget, invoice: Invoice, current: BusinessSettings) -> bool:
    path, _ = QFileDialog.getSaveFileName(
        parent, "Save invoice as PDF", f"Invoice_{invoice.bill_number}.pdf", "PDF (*.pdf)")
    if not path:
        return False
    if not path.lower().endswith(".pdf"):
        path += ".pdf"
    try:
        export_pdf_to(path, invoice, current)
    except (PrintError, OSError) as exc:
        QMessageBox.critical(parent, "Could not save PDF", str(exc))
        return False
    QMessageBox.information(parent, "PDF saved", f"Saved to:\n{path}")
    return True
