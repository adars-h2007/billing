# Shree Wholesale Mobile — Billing & Invoice Printing

Local-first desktop billing app (Python 3.12+, PySide6, SQLite). No internet or browser needed.
The invoice is drawn with real text, lines and shapes (never a photo) using fixed page geometry,
and the **same code** paints the preview, the printer and the PDF export.

## Run

```
pip install -r requirements.txt
python main.py            # database is created at ~/ShreeBilling/billing.db
python main.py --seed     # also insert sample bills
python main.py --db D:\Billing\shop.db   # use a different database file
```
(`SHREE_BILLING_DB` environment variable also sets the database path.)

## Use

1. **New Bill** (Ctrl+N): type name → Enter → address → Enter → mobile → Enter jumps to the item table.
   In the table, Enter moves to the next cell; a new row appears automatically. Ctrl+Enter adds a row.
2. **Save Draft** keeps work in progress. **Save Bill** (Ctrl+S) finalises it.
3. **Print Preview** (Ctrl+P) shows exactly what will print. **Print…** opens the printer dialog
   (choose printer and number of copies). **Export PDF** saves the same layout as a PDF.
4. **Saved Bills** (Ctrl+F): search by bill no., customer, mobile or date; open, reprint, export or delete
   (deleting asks for confirmation).
5. **Business Settings**: shop details, paper size, margins, and database backup.

Finalised bills keep the business header they were issued with, so reprinting an old bill is unchanged
even if you later edit the shop details. Editing a finalised bill always asks for confirmation.

## Calibrating the print (important)

The reference was a photograph, so the real paper size is unknown. Defaults are A4 portrait, 8 mm margins.

1. Settings → choose the paper size (or Custom width × height in mm) and margin. Margins are raised
   automatically to the printer's non-printable area if smaller.
2. Print a test bill on the real stationery. Print at **100% / Actual size** (not "fit to page").
3. If spacing needs adjusting, edit the `Layout` dataclass at the top of `app/printing/invoice_printer.py`
   (all values are in 0.1 mm — e.g. `footer_h`, `line_h`, `particulars_frac`).

## Database

SQLite file with tables `invoices`, `invoice_items`, `business_settings` (created automatically on first run;
foreign keys enforced, bill numbers UNIQUE, money stored as exact decimal text, invoice + items saved in one transaction).

**Backup:** Settings → *Back up database…*, or copy `billing.db` while the app is closed.
**Restore:** close the app and replace `billing.db` with a backup copy.

## Windows executable

On Windows: double-click `build_windows.bat` (or run its commands). Output: `dist\ShreeBilling\ShreeBilling.exe`.
Copy the whole `dist\ShreeBilling` folder to the shop PC.

## Tests

```
pytest            # money, validation, persistence, UI smoke test, PDF rendering/pagination
```
Acceptance items 4–6 and 10 (matching the real paper bill, physical print) need a visual check with
your printer; the tests cover pagination, paper size and PDF output.
