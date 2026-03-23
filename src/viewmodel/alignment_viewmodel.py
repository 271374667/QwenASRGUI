"""对齐页 ViewModel。"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional

from loguru import logger
from PySide6.QtCore import QObject, Property, Signal, Slot
from qthreadwithreturn import QThreadWithReturn

from src.application.app_state import ApplicationState
from src.application.file_support import (
    build_default_export_path,
    build_file_summary,
    ensure_supported_media_file,
    normalize_local_path,
)
from src.application.shared_model_runtime import SharedModelRuntime
from src.application.use_cases import AlignmentUseCase, ExportTextUseCase
from src.infrastructure.qt import QtClipboardGateway, QtFileDialogGateway
from src.viewmodel.page_states import AlignmentPageState


class AlignmentViewModel(QObject):
    """管理强制对齐页的状态和交互。"""

    state_changed = Signal()
    line_items_changed = Signal()
    word_items_changed = Signal()
    language_options_changed = Signal()

    def __init__(
        self,
        application_state: ApplicationState,
        shared_model_runtime: SharedModelRuntime,
        alignment_use_case: AlignmentUseCase,
        export_text_use_case: ExportTextUseCase,
        file_dialog_gateway: QtFileDialogGateway,
        clipboard_gateway: QtClipboardGateway,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._application_state = application_state
        self._shared_model_runtime = shared_model_runtime
        self._alignment_use_case = alignment_use_case
        self._export_text_use_case = export_text_use_case
        self._file_dialog_gateway = file_dialog_gateway
        self._clipboard_gateway = clipboard_gateway
        self._task_thread: Optional[QThreadWithReturn] = None
        self._cancel_requested = False
        self._pending_start_after_model_load = False
        self._line_items: List[Dict[str, Any]] = []
        self._word_items: List[Dict[str, Any]] = []
        self._language_options = [
            {"value": "Auto", "label": "自动"},
            {"value": "Chinese", "label": "中文"},
            {"value": "English", "label": "English"},
            {"value": "Japanese", "label": "Japanese"},
            {"value": "Korean", "label": "Korean"},
            {"value": "French", "label": "French"},
            {"value": "German", "label": "German"},
            {"value": "Spanish", "label": "Spanish"},
            {"value": "Russian", "label": "Russian"},
        ]
        self._local_state = AlignmentPageState()
        self._shared_model_runtime.state_changed.connect(self._on_shared_state_changed)

    @Property("QVariantMap", notify=state_changed)
    def state(self) -> Dict[str, Any]:
        shared_state = self._shared_model_runtime.state
        app_busy = bool(self._application_state.state["isBusy"])
        page_busy = self._local_state.isAligning
        is_busy = page_busy or bool(shared_state["isBusy"])
        model_ready = bool(shared_state["modelReady"])
        local_state = asdict(self._local_state)
        return {
            **local_state,
            "modelReady": model_ready,
            "modelStatusText": shared_state["modelStatusText"],
            "modelName": shared_state["modelName"],
            "modelDetails": shared_state["modelDetails"],
            "loadingProgress": shared_state["loadingProgress"],
            "isBusy": is_busy,
            "isLoadingModel": shared_state["isLoadingModel"],
            "isAligning": page_busy,
            "taskStatusText": self._build_task_status_text(shared_state),
            "lastError": str(self._local_state.lastError or shared_state["lastError"]),
            "canLoadModel": shared_state["canLoadModel"],
            "canReloadModel": shared_state["canReloadModel"],
            "canStartAlignment": (
                bool(self._local_state.selectedFilePath)
                and bool(self._local_state.inputText.strip())
                and (not page_busy)
                and (not app_busy)
            ),
            "canCancelTask": page_busy or bool(shared_state["canCancelTask"]),
            "canExportSubtitle": bool(self._local_state.subtitleText) and (not is_busy),
        }

    @Property("QVariantList", notify=language_options_changed)
    def language_options(self) -> List[Dict[str, str]]:
        return list(self._language_options)

    @Property("QVariantList", notify=line_items_changed)
    def line_items(self) -> List[Dict[str, Any]]:
        return list(self._line_items)

    @Property("QVariantList", notify=word_items_changed)
    def word_items(self) -> List[Dict[str, Any]]:
        return list(self._word_items)

    @Slot(result=bool)
    def pick_input_file(self) -> bool:
        file_path = self._file_dialog_gateway.pick_media_file("选择对齐音频")
        return self.set_selected_file(file_path) if file_path else False

    @Slot(str, result=bool)
    def set_selected_file(self, file_path: str) -> bool:
        normalized = normalize_local_path(file_path)
        if not normalized or not ensure_supported_media_file(normalized):
            self._set_error("请选择受支持的音频或视频文件")
            return False

        summary = build_file_summary(normalized)
        self.clear_result()
        self._local_state.selectedFilePath = normalized
        self._local_state.selectedFileName = summary["fileName"]
        self._local_state.fileSuffix = summary["fileSuffix"]
        self._local_state.fileSizeText = summary["fileSizeText"]
        self._pending_start_after_model_load = False
        self._local_state.taskStatusText = "音频已就绪，可开始对齐"
        self._local_state.lastError = ""
        self.state_changed.emit()
        return True

    @Slot(str)
    def update_input_text(self, text: str) -> None:
        self._local_state.inputText = text
        self._local_state.lastError = ""
        if not text.strip():
            self._pending_start_after_model_load = False
        self.state_changed.emit()

    @Slot(str)
    def update_language(self, language_value: str) -> None:
        self._local_state.selectedLanguage = language_value
        self.state_changed.emit()

    @Slot()
    def load_model(self) -> None:
        self._pending_start_after_model_load = False
        self._shared_model_runtime.load_model()

    @Slot()
    def load_model_and_continue(self) -> None:
        if self._shared_model_runtime.state["modelReady"]:
            self.start_alignment()
            return

        self._pending_start_after_model_load = True
        self._local_state.taskStatusText = "正在加载共享模型，完成后将自动开始对齐..."
        self._local_state.lastError = ""
        self.state_changed.emit()
        self._shared_model_runtime.load_model()

        shared_state = self._shared_model_runtime.state
        if (not shared_state["isBusy"]) and (not shared_state["modelReady"]):
            self._pending_start_after_model_load = False

    @Slot()
    def reload_model(self) -> None:
        self._pending_start_after_model_load = False
        self._shared_model_runtime.reload_model()

    @Slot()
    def start_alignment(self) -> None:
        if not self._local_state.selectedFilePath:
            self._set_error("请先选择音频文件")
            return
        if not self._local_state.inputText.strip():
            self._set_error("请输入待对齐文本")
            return
        if not self._shared_model_runtime.state["modelReady"]:
            self._set_error("共享模型尚未加载，请先加载模型")
            return
        if not self._application_state.begin_operation("强制对齐"):
            self._set_error("已有后台任务正在运行，请稍后再试")
            return

        self._local_state.isAligning = True
        self._local_state.taskStatusText = "正在执行强制对齐..."
        self._local_state.lastError = ""
        self._cancel_requested = False
        self.state_changed.emit()

        thread = QThreadWithReturn(self._align_worker, thread_name="align")
        thread.setParent(self)
        self._task_thread = thread
        thread.add_done_callback(self._on_alignment_completed)
        thread.add_failure_callback(self._on_task_error)
        thread.finished_signal.connect(self._on_task_finished)
        thread.start()

    @Slot(result=bool)
    def cancel_current_task(self) -> bool:
        if self._task_thread is not None and self._task_thread.running():
            self._cancel_requested = True
            self._local_state.taskStatusText = "正在强制停止当前任务..."
            self._local_state.lastError = ""
            self.state_changed.emit()
            return self._task_thread.cancel(force_stop=True)
        return self._shared_model_runtime.cancel_current_task()

    @Slot()
    def shutdown(self) -> None:
        if self._task_thread is not None and self._task_thread.running():
            self._task_thread.cancel(force_stop=True)

    @Slot(result=bool)
    def export_subtitle_with_dialog(self) -> bool:
        default_path = build_default_export_path(self._local_state.selectedFilePath, ".srt")
        file_path = self._file_dialog_gateway.save_subtitle("导出对齐字幕", default_path)
        return self.export_subtitle(file_path) if file_path else False

    @Slot(str, result=bool)
    def export_subtitle(self, file_path: str) -> bool:
        return self._export_text_use_case.execute(
            file_path,
            self._local_state.subtitleText,
            "对齐字幕已导出: {path}",
        )

    @Slot(result=bool)
    def copy_subtitle(self) -> bool:
        return self._clipboard_gateway.copy_text(self._local_state.subtitleText)

    @Slot(result=bool)
    def copy_raw_timestamps(self) -> bool:
        return self._clipboard_gateway.copy_text(self._local_state.rawTimestampText)

    @Slot()
    def clear_result(self) -> None:
        self._line_items = []
        self._word_items = []
        self._local_state.audioDurationText = "--"
        self._local_state.wordCount = 0
        self._local_state.lineCount = 0
        self._local_state.subtitleText = ""
        self._local_state.rawTimestampText = ""
        self._local_state.lastError = ""
        self._local_state.hasResult = False
        self.line_items_changed.emit()
        self.word_items_changed.emit()
        self.state_changed.emit()

    def _build_task_status_text(self, shared_state: Dict[str, Any]) -> str:
        if self._local_state.isAligning:
            return self._local_state.taskStatusText
        if shared_state["isBusy"]:
            return str(shared_state["taskStatusText"])
        if self._local_state.lastError:
            return self._local_state.lastError
        if self._local_state.hasResult:
            return "对齐完成，可导出字幕"
        if (
            self._local_state.selectedFilePath
            and self._local_state.inputText.strip()
            and shared_state["modelReady"]
        ):
            return "音频与文本已就绪，可开始对齐"
        if self._local_state.selectedFilePath and self._local_state.inputText.strip():
            return "音频与文本已就绪，开始对齐时会提示加载模型"
        return "请选择音频并输入待对齐文本"

    def _align_worker(self) -> Dict[str, Any]:
        return self._alignment_use_case.execute(
            self._local_state.selectedFilePath,
            self._local_state.inputText,
            self._local_state.selectedLanguage,
        )

    def _set_error(self, message: str) -> None:
        self._local_state.lastError = message
        self._local_state.taskStatusText = message
        self.state_changed.emit()
        logger.error(message)

    def _on_shared_state_changed(self) -> None:
        shared_state = self._shared_model_runtime.state
        if self._pending_start_after_model_load:
            if (
                shared_state["modelReady"]
                and (not shared_state["isBusy"])
                and (not self._application_state.state["isBusy"])
                and (not self._local_state.isAligning)
            ):
                self._pending_start_after_model_load = False
                self.start_alignment()
                return
            if (not shared_state["isBusy"]) and (not shared_state["modelReady"]):
                self._pending_start_after_model_load = False
        self.state_changed.emit()

    def _on_alignment_completed(self, payload: object) -> None:
        data = dict(payload or {})
        self._line_items = list(data.get("lineItems", []))
        self._word_items = list(data.get("wordItems", []))
        self._local_state.audioDurationText = data.get("audioDurationText", "--")
        self._local_state.wordCount = data.get("wordCount", 0)
        self._local_state.lineCount = data.get("lineCount", 0)
        self._local_state.subtitleText = data.get("subtitleText", "")
        self._local_state.rawTimestampText = data.get("rawTimestampText", "")
        self._local_state.taskStatusText = "对齐完成，可导出字幕"
        self._local_state.lastError = ""
        self._local_state.hasResult = True
        self.line_items_changed.emit()
        self.word_items_changed.emit()
        self.state_changed.emit()

    def _on_task_error(self, error: object) -> None:
        message = str(error)
        self._local_state.lastError = message
        self._local_state.taskStatusText = message
        self.state_changed.emit()

    def _on_task_finished(self) -> None:
        thread = self._task_thread
        self._task_thread = None
        self._local_state.isAligning = False
        if self._cancel_requested:
            self._local_state.taskStatusText = "任务已强制停止"
            self._local_state.lastError = ""
        self._cancel_requested = False
        self._application_state.finish_operation()
        self.state_changed.emit()
        if thread is not None:
            thread.deleteLater()
