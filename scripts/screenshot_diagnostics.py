"""Generate diagnostics page screenshot at 1440x900."""

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


SAMPLE_RECORDS = [
    {
        "start_time": "2026-06-24 10:00:00",
        "sync_type": "物料同步",
        "table_name": "bd_material",
        "status": "failed",
        "message": "字段 FNumber 转换失败，请检查字段映射配置",
    },
    {
        "start_time": "2026-06-24 10:18:00",
        "sync_type": "客户同步",
        "table_name": "bd_customer",
        "status": "partial",
        "message": "部分记录缺少必填字段",
    },
]


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
        patch(
            "src.gui.pages.diagnostics_page.get_dashboard_today_stats",
            return_value={"pending_count": 2, "fail_count": 2},
        ),
        patch("src.gui.pages.diagnostics_page.history_manager.get_history", return_value=(SAMPLE_RECORDS, 2)),
        patch(
            "src.gui.pages.diagnostics_page.history_manager.get_stats",
            return_value={"top_failures": ["字段 FNumber 转换失败", "部分记录缺少必填字段"]},
        ),
    ):
        gui = KingdeeSyncGUI()
        gui.kd_connected = True
        gui.db_connected = True
        gui.resize(1440, 900)
        gui.show()
        app.processEvents()

        gui.switch_to_page("diagnostics")
        app.processEvents()
        app.processEvents()

        pixmap = QPixmap(gui.size())
        gui.render(pixmap)
        out = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "docs",
            "screenshots",
            "diagnostics_final_tuned_1440x900.png",
        )
        pixmap.save(out)
        print(f"Saved: {out}")
        gui.close()


if __name__ == "__main__":
    main()
