"""Generate log center page screenshot at 1440x900."""

# ruff: noqa: E402, I001

import glob
import json
import os
import sys
import tempfile
from datetime import datetime
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_OPENGL", "software")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase, QPixmap
from PySide6.QtWidgets import QApplication


def _write_sample_logs(log_dir: str) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    entries = [
        {
            "asctime": f"{today} 09:00:00",
            "levelname": "INFO",
            "name": "src.core.kingdee_api",
            "message": "T_BD_Material 获取金蝶数据成功",
        },
        {
            "asctime": f"{today} 09:05:00",
            "levelname": "ERROR",
            "name": "src.core.form_sync_runner",
            "message": "T_BD_Customer 写入失败：字段 FNumber 不能为空",
        },
        {
            "asctime": f"{today} 09:10:00",
            "levelname": "WARNING",
            "name": "src.core.scheduler",
            "message": "调度服务等待下一次执行",
        },
        {
            "asctime": f"{today} 09:12:00",
            "levelname": "INFO",
            "name": "src.core.data_sync",
            "message": "T_SAL_SaleOrder 同步完成，写入 128 条",
        },
    ]
    with open(os.path.join(log_dir, "app.jsonl"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(json.dumps(entry, ensure_ascii=False) for entry in entries))


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

    with tempfile.TemporaryDirectory() as tmpdir:
        _write_sample_logs(tmpdir)
        with (
            patch("src.gui.kingdee_sync_gui.QTimer.singleShot", lambda *_args, **_kwargs: None),
            patch("src.gui.pages.log_center_page._get_log_dir", return_value=tmpdir),
        ):
            gui = KingdeeSyncGUI()
            gui.kd_connected = True
            gui.db_connected = True
            gui.resize(1440, 900)
            gui.show()
            app.processEvents()

            gui.switch_to_page("log_center")
            app.processEvents()
            app.processEvents()

            pixmap = QPixmap(gui.size())
            gui.render(pixmap)
            out = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "docs",
                "screenshots",
                "log_center_final_tuned_1440x900.png",
            )
            pixmap.save(out)
            print(f"Saved: {out}")
            gui.close()


if __name__ == "__main__":
    main()
