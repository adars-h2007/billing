# Shree Wholesale Mobile — Billing & Invoice Printing

A desktop billing and invoice printing system built for **Shree Wholesale Mobile**, a mobile accessories and spare parts wholesale shop in Ichalkaranji. It creates bills quickly and prints invoices that match the shop's existing paper bill.

## Features

- Create and save customer bills
- Print-ready invoices that reproduce the shop's paper bill:
  - Dark-red theme
  - Two-column **Particulars / Amount** table
  - Total row
  - Receiver's signature footer
- Print directly through the system print dialog
- Local SQLite database, so there is no internet or server setup for the desktop app
- Packaged as a Windows `.exe` so it runs without installing Python

## Tech used

| Purpose | Technology |
|---|---|
| Language | Python 3.12+ |
| Desktop UI | PySide6 (Qt) |
| Database | SQLite |
| Invoice layout | HTML/CSS rendered through Qt |
| Printing | `QPrinter` / `QPrintDialog` |
| Packaging | PyInstaller (Windows exe) |

## Getting started

### Prerequisites

- Python 3.12 or newer

### Installation

```bash
git clone https://github.com/adars-h2007/<repo-name>.git
cd <repo-name>
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install PySide6
python main.py
```

<!-- Replace <repo-name> with your repository name and main.py with your app's entry file.
If you keep a requirements.txt, use: pip install -r requirements.txt -->

## Build a Windows executable

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile main.py
```

The executable is created in the `dist/` folder.

> The desktop app runs on Windows. Build the `.exe` on a Windows machine.

## Printing

The invoice is laid out in HTML and CSS and drawn by Qt, so what you see on the preview is what is printed. To change the look of the bill, edit the invoice template and its styles.

## Roadmap

- [ ] Mobile version as an installable web app (PWA)
- [ ] Phone and shop PC sharing the same bills through an online server with login

## Author

**Adarsh Patil**

- GitHub: [@adars-h2007](https://github.com/adars-h2007)
- LinkedIn: [Adarsh Patil](https://www.linkedin.com/in/adarsh-patil-587a65319/)
- Email: adarshpatil6650@gmail.com
