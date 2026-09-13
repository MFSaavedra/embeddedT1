"""Entry point of the PyQt application.

Run from the repository root:   python gui_python/main.py
"""
import sys

from PyQt5.QtWidgets import QApplication

from main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1280, 800)
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
