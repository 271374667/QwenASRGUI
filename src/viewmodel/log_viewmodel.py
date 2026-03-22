"""日志页 ViewModel。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, Property, Signal, Slot

from src.application.app_state import ApplicationState
from src.application.log_store import LogStore


class LogViewModel(QObject):
    """管理日志页的数据和命令。

    该 ViewModel 将日志条目与全局任务状态组合后提供给 QML 页面，
    页面只需要依赖当前 ViewModel 即可完成日志展示、导出和清空。

    Attributes:
        state_changed: 页面状态变化通知。
        entries_changed: 日志条目变化通知。

    Example:
        基本用法示例::

            view_model = LogViewModel(app_state, log_store)
            total = view_model.entry_count

    Note:
        日志筛选逻辑仍保留在 QML 侧，ViewModel 仅提供原始条目和操作命令。
    """

    state_changed = Signal()
    entries_changed = Signal()

    def __init__(
        self,
        application_state: ApplicationState,
        log_store: LogStore,
        parent: Optional[QObject] = None,
    ) -> None:
        """初始化日志页 ViewModel。"""
        super().__init__(parent)
        self._application_state = application_state
        self._log_store = log_store
        self._application_state.state_changed.connect(self.state_changed.emit)
        self._log_store.entries_changed.connect(self.entries_changed.emit)

    @Property("QVariantMap", notify=state_changed)
    def state(self) -> Dict[str, Any]:
        """返回日志页状态。"""
        return {
            "currentOperation": self._application_state.state["currentOperation"],
        }

    @Property("QVariantList", notify=entries_changed)
    def entries(self) -> List[Dict[str, str]]:
        """返回日志条目。"""
        return self._log_store.entries

    @Property(int, notify=entries_changed)
    def entry_count(self) -> int:
        """返回日志条目数量。"""
        return self._log_store.entry_count

    @Slot()
    def clear_entries(self) -> None:
        """清空日志。"""
        self._log_store.clear_entries()

    @Slot(result=bool)
    def export_logs_with_dialog(self) -> bool:
        """通过对话框导出日志。"""
        return self._log_store.export_logs_with_dialog()
