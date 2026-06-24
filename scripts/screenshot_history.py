"""Generate history page screenshots - real state and sample data state."""
import glob
import os
import sys
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase, QPixmap
from PySide6.QtWidgets import QApplication

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_OPENGL", "software")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = QApplication.instance()
if app is None:
    QApplication.setAttribute(Qt.AA_Use96Dpi, True)
    app = QApplication(["screenshot"])
app.setQuitOnLastWindowClosed(False)

for pattern in [r"C:\Windows\Fonts\msyh*.ttc", r"C:\Windows\Fonts\msyh*.ttf"]:
    for f in glob.glob(pattern):
        QFontDatabase.addApplicationFont(f)
app.setFont(QFont("Microsoft YaHei", 13))

from src.gui.kingdee_sync_gui import KingdeeSyncGUI

SAMPLE_RECORDS = [
    {"start_time": "2024-05-14 10:15:32", "sync_type": "物料基础资料同步", "table_name": "T_BD_Material", "status": "success", "record_count": 8542, "duration_seconds": 92, "message": ""},
    {"start_time": "2024-05-14 10:10:21", "sync_type": "客户资料同步", "table_name": "T_BD_Customer", "status": "success", "record_count": 3215, "duration_seconds": 58, "message": ""},
    {"start_time": "2024-05-14 10:05:18", "sync_type": "销售订单同步", "table_name": "T_SAL_SaleOrder", "status": "failed", "record_count": 128, "duration_seconds": 45, "message": "字段映射错误：FNumber"},
    {"start_time": "2024-05-14 10:00:11", "sync_type": "采购订单同步", "table_name": "T_PUR_PurchaseOrder", "status": "success", "record_count": 1245, "duration_seconds": 72, "message": ""},
    {"start_time": "2024-05-14 09:55:07", "sync_type": "库存余额同步", "table_name": "T_INV_Stock", "status": "partial", "record_count": 5321, "duration_seconds": 125, "message": "部分数据校验失败"},
    {"start_time": "2024-05-14 09:50:33", "sync_type": "应收应付余额同步", "table_name": "T_AR_AP_Balance", "status": "success", "record_count": 2145, "duration_seconds": 61, "message": ""},
    {"start_time": "2024-05-14 09:45:12", "sync_type": "凭证信息同步", "table_name": "T_GL_Voucher", "status": "failed", "record_count": 0, "duration_seconds": 33, "message": "连接超时"},
    {"start_time": "2024-05-14 09:30:05", "sync_type": "物料基础资料同步", "table_name": "T_BD_Material", "status": "success", "record_count": 8756, "duration_seconds": 88, "message": ""},
]

def make_gui():
    gui = KingdeeSyncGUI()
    gui.kd_connected = True
    gui.db_connected = True
    gui.resize(1440, 900)
    gui.show()
    app.processEvents()
    return gui

# --- Screenshot 1: Real state (empty) ---
gui = make_gui()
gui.switch_to_page("history")
app.processEvents()
app.processEvents()
pixmap = QPixmap(gui.size())
gui.render(pixmap)
out1 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "screenshots", "history_after_1440x900.png")
pixmap.save(out1)
print(f"Saved: {out1}")
gui.close()

# --- Screenshot 2: Sample data state ---
with patch("src.gui.pages.history_page.history_manager.get_history", return_value=(SAMPLE_RECORDS, 8)):
    with patch("src.gui.pages.history_page.history_manager.get_stats", return_value={
        "today_success_rate": "82.45%", "avg_duration": "12.38s", "top_failures": []
    }):
        gui2 = make_gui()
        gui2.switch_to_page("history")
        app.processEvents()
        app.processEvents()
        pixmap2 = QPixmap(gui2.size())
        gui2.render(pixmap2)
        out2 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "screenshots", "history_sample_after_1440x900.png")
        pixmap2.save(out2)
        print(f"Saved: {out2}")
        gui2.close()
