"""应用组合根。"""

from __future__ import annotations

from src.application.app_state import ApplicationState
from src.application.log_store import LogStore
from src.application.settings_store import SettingsStore
from src.application.shared_model_runtime import SharedModelRuntime
from src.application.use_cases import (
    AlignmentUseCase,
    ExportTextUseCase,
    TranscriptionUseCase,
)
from src.infrastructure.qt import QtClipboardGateway, QtFileDialogGateway
from src.viewmodel.alignment_viewmodel import AlignmentViewModel
from src.viewmodel.log_viewmodel import LogViewModel
from src.viewmodel.settings_viewmodel import SettingsViewModel
from src.viewmodel.transcription_viewmodel import TranscriptionViewModel


class CompositionRoot:
    """负责组装应用层、基础设施层与 ViewModel 层对象。"""

    def __init__(self) -> None:
        self.application_state = ApplicationState()
        self.settings_store = SettingsStore()
        self.log_store = LogStore()
        self.shared_model_runtime = SharedModelRuntime(
            self.application_state,
            self.settings_store,
        )

        self.file_dialog_gateway = QtFileDialogGateway()
        self.clipboard_gateway = QtClipboardGateway()

        self.export_text_use_case = ExportTextUseCase()
        self.transcription_use_case = TranscriptionUseCase(
            self.settings_store,
            self.shared_model_runtime,
        )
        self.alignment_use_case = AlignmentUseCase(
            self.settings_store,
            self.shared_model_runtime,
        )

        self.transcription_view_model = TranscriptionViewModel(
            self.application_state,
            self.shared_model_runtime,
            self.transcription_use_case,
            self.export_text_use_case,
            self.file_dialog_gateway,
            self.clipboard_gateway,
        )
        self.alignment_view_model = AlignmentViewModel(
            self.application_state,
            self.shared_model_runtime,
            self.alignment_use_case,
            self.export_text_use_case,
            self.file_dialog_gateway,
            self.clipboard_gateway,
        )
        self.log_view_model = LogViewModel(
            self.application_state,
            self.log_store,
            self.file_dialog_gateway,
        )
        self.settings_view_model = SettingsViewModel(
            self.application_state,
            self.settings_store,
            self.shared_model_runtime,
        )

    def shutdown(self) -> None:
        self.transcription_view_model.shutdown()
        self.alignment_view_model.shutdown()
        self.shared_model_runtime.shutdown()
        self.application_state.shutdown()
        self.log_store.shutdown()
