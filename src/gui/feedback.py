"""
Unified dialog and feedback helpers.
"""

from PySide6.QtWidgets import QMessageBox, QWidget


class UiFeedback:
    """Unified message feedback entrypoint."""

    @staticmethod
    def build_error_message(summary: str, detail: object | None = None) -> str:
        detail_text = str(detail).strip() if detail is not None else ""
        if detail_text:
            return f"{summary}\n\n详细信息：{detail_text}"
        return summary

    @staticmethod
    def success(parent: QWidget | None, title: str = "操作成功", message: str = ""):
        return QMessageBox.information(parent, title, message)

    @staticmethod
    def info(parent: QWidget | None, title: str = "提示", message: str = ""):
        return QMessageBox.information(parent, title, message)

    @staticmethod
    def warning(parent: QWidget | None, title: str = "注意", message: str = ""):
        return QMessageBox.warning(parent, title, message)

    @staticmethod
    def error(parent: QWidget | None, title: str = "操作失败", message: str = ""):
        return QMessageBox.critical(parent, title, message)

    @staticmethod
    def confirm(
        parent: QWidget | None,
        title: str = "请确认",
        message: str = "",
        default_button=QMessageBox.No,
    ):
        return QMessageBox.question(
            parent,
            title,
            message,
            QMessageBox.Yes | QMessageBox.No,
            default_button,
        )
