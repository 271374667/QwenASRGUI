"""日志桥接服务。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtWidgets import QFileDialog

from src.service.service_utils import LOG_FILE_FILTER, normalize_local_path


class LogService(QObject):
    """将 Loguru 日志桥接到 QML 的服务。

    该服务负责接收来自主线程和后台线程的日志记录，并将其转换为适合 QML
    绑定的结构化列表。日志页面可以直接消费 `entries` 属性，同时服务也提供
    清空和导出能力。

    Attributes:
        entries_changed: 日志列表变化通知。

    Example:
        基本用法::

            log_service = LogService()
            log_service.install_sink()
            logger.info("hello")
            print(log_service.entries)

    Note:
        为避免跨线程直接修改 Qt 对象，Loguru sink 先发射内部信号，再由主线程
        追加日志条目。
    """

    entries_changed = Signal()
    _queued_entry = Signal(str, str, str, str)

    def __init__(
        self,
        parent: Optional[QObject] = None,
        max_entries: int = 2000,
    ) -> None:
        """初始化日志服务。"""
        super().__init__(parent)
        self._entries: List[Dict[str, str]] = []
        self._max_entries = max_entries
        self._sink_id: Optional[int] = None
        self._queued_entry.connect(self._append_entry)

    @Property("QVariantList", notify=entries_changed)
    def entries(self) -> List[Dict[str, str]]:
        """返回日志条目列表。"""
        return list(self._entries)

    @Property(int, notify=entries_changed)
    def entry_count(self) -> int:
        """返回当前日志数量。"""
        return len(self._entries)

    def install_sink(self) -> None:
        """安装 Loguru sink。"""
        if self._sink_id is not None:
            return

        self._sink_id = logger.add(
            self._receive_loguru_message,
            level="DEBUG",
            enqueue=False,
            backtrace=False,
            diagnose=False,
        )

    def shutdown(self) -> None:
        """移除已安装的 Loguru sink。"""
        if self._sink_id is not None:
            logger.remove(self._sink_id)
            self._sink_id = None

    @Slot()
    def clear_entries(self) -> None:
        """清空日志记录。"""
        self._entries.clear()
        self.entries_changed.emit()

    @Slot(result=bool)
    def export_logs_with_dialog(self) -> bool:
        """通过文件对话框导出日志。"""
        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "导出日志",
            str(Path.cwd() / "qwenasr.log"),
            LOG_FILE_FILTER,
        )
        if not file_path:
            return False
        return self.export_logs(file_path)

    @Slot(str, result=bool)
    def export_logs(self, file_path: str) -> bool:
        """导出日志到指定文件。"""
        normalized = normalize_local_path(file_path)
        if not normalized:
            return False

        output_path = Path(normalized)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(
            f"[{item['timestamp']}] [{item['level']}] {item['source']} - {item['message']}"
            for item in self._entries
        )
        output_path.write_text(content, encoding="utf-8")
        return True

    def _receive_loguru_message(self, message: Any) -> None:
        """接收 Loguru 消息并转发到主线程。"""
        record = message.record
        self._queued_entry.emit(
            record["time"].strftime("%H:%M:%S"),
            record["level"].name,
            record["name"].split(".")[-1],
            record["message"],
        )

    @Slot(str, str, str, str)
    def _append_entry(
        self,
        timestamp: str,
        level: str,
        source: str,
        message: str,
    ) -> None:
        """在主线程中追加日志条目。"""
        self._entries.append(
            {
                "timestamp": timestamp,
                "level": level,
                "source": source,
                "message": message,
            }
        )

        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries :]

        self.entries_changed.emit()
