"""Entry point:  python main.py [--db path/to/billing.db] [--seed]"""
import argparse
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from app.database import Database, default_db_path
from app.ui.main_window import MainWindow


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(default_db_path()), help="SQLite database file")
    ap.add_argument("--seed", action="store_true", help="insert sample development data")
    args, qt_args = ap.parse_known_args()

    app = QApplication([sys.argv[0], *qt_args])
    app.setApplicationName("Shree Billing")
    from app.ui.theme import apply_light_theme
    apply_light_theme(app)
    try:
        db = Database(args.db)
    except Exception as exc:  # noqa: BLE001
        QMessageBox.critical(None, "Cannot open database", f"{args.db}\n\n{exc}")
        return 1
    if args.seed:
        from app.sample_data import seed
        seed(db)
    window = MainWindow(db)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
