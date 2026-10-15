@echo off
REM Build ShreeBilling.exe (run on Windows, in this folder).
py -3.12 -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt
pyinstaller --noconfirm --windowed --name ShreeBilling main.py
echo.
echo Done. Run dist\ShreeBilling\ShreeBilling.exe
