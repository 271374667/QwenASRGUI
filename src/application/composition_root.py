"""应用组合根。"""

from __future__ import annotations

from src.application.app_state import ApplicationState
from src.application.log_store import LogStore
from src.application.settings_store import SettingsStore
from src.application.shared_model_runtime import SharedModelRuntime
from src.viewmodel import (
    AlignmentViewModel,
    LogViewModel,
    SettingsViewModel,
    TranscriptionViewModel,
)


class CompositionRoot:
    """负责组装应用层与 ViewModel 层对象。"""

    def __init__(self) -> None:
        """初始化应用对象图。"""
        self.log_store = LogStore()
        self.application_state = ApplicationState()
        self.settings_store = SettingsStore()
        self.shared_model_runtime = SharedModelRuntime(
            self.application_state,
            self.settings_store,
        )
        self.transcription_view_model = TranscriptionViewModel(
            self.application_state,
            self.settings_store,
            self.shared_model_runtime,
        )
        self.alignment_view_model = AlignmentViewModel(
            self.application_state,
            self.settings_store,
            self.shared_model_runtime,
        )
        self.log_view_model = LogViewModel(
            self.application_state,
            self.log_store,
        )
        self.settings_view_model = SettingsViewModel(
            self.application_state,
            self.settings_store,
            self.shared_model_runtime,
        )

    def shutdown(self) -> None:
        """关闭后台任务和资源。"""
        self.transcription_view_model.shutdown()
        self.alignment_view_model.shutdown()
        self.shared_model_runtime.shutdown()
        self.application_state.shutdown()
        self.log_store.shutdown()
