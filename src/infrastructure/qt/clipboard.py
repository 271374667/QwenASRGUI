"""Qt 剪贴板基础设施。"""

from __future__ import annotations

from PySide6.QtGui import QGuiApplication


class QtClipboardGateway:
    """封装 Qt 剪贴板访问。"""

    def copy_text(self, text: str) -> bool:
        """复制文本到系统剪贴板。"""
        if not text:
            return False

        clipboard = QGuiApplication.clipboard()
        clipboard.setText(text)
        return True
