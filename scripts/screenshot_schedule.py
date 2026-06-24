"""Generate schedule page screenshot at 1440x900."""

# ruff: noqa: E402, I001

import glob
import os
import sys
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_OPENGL", "software")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase, QPixmap
from PySide6.QtWidgets import QApplication


def main() -> None:
    app = QApplication.instance()
    if app is None:
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_Use96Dpi, True)
        app = QApplication(["screenshot"])
    app.setQuitOnLastWindowClosed(False)

    for pattern in [r"C:\Windows\Fonts\msyh*.ttc", r"C:\Windows\Fonts\msyh*.ttf"]:
        for font_file in glob.glob(pattern):
            QFontDatabase.addApplicationFont(font_file)
    app.setFont(QFont("Microsoft YaHei", 13))

    from src.gui.kingdee_sync_gui import KingdeeSyncGUI

    with (
        patch("src.gui.kingdee_sync_gui.QTimer.singleShot", lambda *_args, **_kwargs: None),
        patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=True),
        patch(
            "src.gui.pages.schedule_page.config_manager.get_sync_config",
            return_value={"auto_sync": True, "sync_interval": 30},
        ),
    ):
        gui = KingdeeSyncGUI()
        gui.kd_connected = True
        gui.db_connected = True
        gui.resize(1440, 900)
        gui.show()
        app.processEvents()

        gui.switch_to_page("schedule")
        app.processEvents()
        app.processEvents()

        pixmap = QPixmap(gui.size())
        gui.render(pixmap)
        out = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "docs",
            "screenshots",
            "schedule_final_tuned_1440x900.png",
        )
        pixmap.save(out)
        print(f"Saved: {out}")
        gui.close()


if __name__ == "__main__":
    main()
