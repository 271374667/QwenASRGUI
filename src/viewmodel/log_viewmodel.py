"""日志页 ViewModel。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, Property, Signal, Slot

from src.application.app_state import ApplicationState
from src.application.log_store import LogStore
from src.infrastructure.qt import QtFileDialogGateway


class LogViewModel(QObject):
    """管理日志页的数据和命令。"""

    state_changed = Signal()
    entries_changed = Signal()

    def __init__(
        self,
        application_state: ApplicationState,
        log_store: LogStore,
        file_dialog_gateway: QtFileDialogGateway,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._application_state = application_state
        self._log_store = log_store
        self._file_dialog_gateway = file_dialog_gateway
        self._application_state.state_changed.connect(self.state_changed.emit)
        self._log_store.entries_changed.connect(self.entries_changed.emit)

    @Property("QVariantMap", notify=state_changed)
    def state(self) -> Dict[str, Any]:
        return {
            "currentOperation": self._application_state.state["currentOperation"],
        }

    @Property("QVariantList", notify=entries_changed)
    def entries(self) -> List[Dict[str, str]]:
        return self._log_store.entries

    @Property(int, notify=entries_changed)
    def entry_count(self) -> int:
        return self._log_store.entry_count

    @Slot()
    def clear_entries(self) -> None:
        self._log_store.clear_entries()

    @Slot(result=bool)
    def export_logs_with_dialog(self) -> bool:
        file_path = self._file_dialog_gateway.save_logs(str(Path.cwd() / "qwenasr.log"))
        return self._log_store.export_logs(file_path) if file_path else False
