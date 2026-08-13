from __future__ import annotations

import sys
from typing import Any

from PySide6.QtWidgets import QApplication

from mxd_bot.gui_app import MainWindow


def run_gui(config: dict[str, Any]) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(config)
    window.show()
    app.exec()
