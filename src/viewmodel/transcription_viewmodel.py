"""转录页 ViewModel。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtWidgets import QFileDialog
from qthreadwithreturn import QThreadWithReturn

from src.application.app_state import ApplicationState
from src.application.file_support import (
    MEDIA_FILE_FILTER,
    SRT_FILE_FILTER,
    TEXT_FILE_FILTER,
    build_default_export_path,
    build_file_summary,
    ensure_supported_media_file,
    format_duration,
    normalize_local_path,
    serialize_aggregated_lines,
    serialize_time_stamps,
)
from src.application.settings_store import SettingsStore
from src.application.shared_model_runtime import SharedModelRuntime


class TranscriptionViewModel(QObject):
    """管理转录页的状态、命令与共享模型协作。

    该 ViewModel 位于 MVVM 架构中的表示层，负责维护转录页的局部状态，
    并通过 `SharedModelRuntime` 访问共享模型能力。QML 页面仅依赖该
    ViewModel，而不会直接接触应用状态或设置存储。

    Attributes:
        state_changed: 页面状态变化通知。
        timeline_items_changed: 字幕时间线变化通知。
        raw_timestamp_items_changed: 原始时间戳变化通知。

    Example:
        基本用法示例::

            view_model = TranscriptionViewModel(app_state, settings_store, shared_model_runtime)
            view_model.pick_input_file()
            view_model.start_transcription()

    Note:
        共享模型状态来自 `SharedModelRuntime`，页面局部状态由当前 ViewModel 自行维护。
    """

    state_changed = Signal()
    timeline_items_changed = Signal()
    raw_timestamp_items_changed = Signal()

    def __init__(
        self,
        application_state: ApplicationState,
        settings_store: SettingsStore,
        shared_model_runtime: SharedModelRuntime,
        parent: Optional[QObject] = None,
    ) -> None:
        """初始化转录页 ViewModel。"""
        super().__init__(parent)
        self._application_state = application_state
        self._settings_store = settings_store
        self._shared_model_runtime = shared_model_runtime
        self._task_thread: Optional[QThreadWithReturn] = None
        self._cancel_requested = False
        self._timeline_items: List[Dict[str, Any]] = []
        self._raw_timestamp_items: List[Dict[str, Any]] = []
        self._local_state: Dict[str, Any] = {
            "selectedFilePath": "",
            "selectedFileName": "未选择媒体文件",
            "fileSuffix": "--",
            "fileSizeText": "--",
            "isTranscribing": False,
            "language": "--",
            "durationText": "--",
            "subtitleLineCount": 0,
            "timestampCount": 0,
            "transcriptText": "",
            "subtitleText": "",
            "lastError": "",
            "taskStatusText": "请选择媒体文件并加载模型",
            "hasResult": False,
        }
        self._shared_model_runtime.state_changed.connect(self._on_shared_state_changed)

    @Property("QVariantMap", notify=state_changed)
    def state(self) -> Dict[str, Any]:
        """返回供 QML 绑定的页面状态。"""
        shared_state = self._shared_model_runtime.state
        app_busy = bool(self._application_state.state["isBusy"])
        model_ready = bool(shared_state["modelReady"])
        page_busy = bool(self._local_state["isTranscribing"])
        is_busy = page_busy or bool(shared_state["isBusy"])
        task_status_text = self._build_task_status_text(shared_state)
        last_error = str(self._local_state["lastError"] or shared_state["lastError"])
        return {
            "selectedFilePath": self._local_state["selectedFilePath"],
            "selectedFileName": self._local_state["selectedFileName"],
            "fileSuffix": self._local_state["fileSuffix"],
            "fileSizeText": self._local_state["fileSizeText"],
            "modelReady": model_ready,
            "modelStatusText": shared_state["modelStatusText"],
            "modelName": shared_state["modelName"],
            "modelDetails": shared_state["modelDetails"],
            "loadingProgress": shared_state["loadingProgress"],
            "isBusy": is_busy,
            "isLoadingModel": shared_state["isLoadingModel"],
            "isTranscribing": page_busy,
            "taskStatusText": task_status_text,
            "language": self._local_state["language"],
            "durationText": self._local_state["durationText"],
            "subtitleLineCount": self._local_state["subtitleLineCount"],
            "timestampCount": self._local_state["timestampCount"],
            "transcriptText": self._local_state["transcriptText"],
            "subtitleText": self._local_state["subtitleText"],
            "lastError": last_error,
            "hasResult": self._local_state["hasResult"],
            "canLoadModel": shared_state["canLoadModel"],
            "canUnloadModel": shared_state["canUnloadModel"],
            "canReloadModel": shared_state["canReloadModel"],
            "canStartTranscription": (
                bool(self._local_state["selectedFilePath"])
                and model_ready
                and (not page_busy)
                and (not app_busy)
            ),
            "canCancelTask": page_busy or bool(shared_state["canCancelTask"]),
            "canExportTranscript": bool(self._local_state["transcriptText"]) and (not is_busy),
            "canExportSubtitle": bool(self._local_state["subtitleText"]) and (not is_busy),
        }

    @Property("QVariantList", notify=timeline_items_changed)
    def timeline_items(self) -> List[Dict[str, Any]]:
        """返回聚合后的字幕时间线。"""
        return list(self._timeline_items)

    @Property("QVariantList", notify=raw_timestamp_items_changed)
    def raw_timestamp_items(self) -> List[Dict[str, Any]]:
        """返回原始时间戳列表。"""
        return list(self._raw_timestamp_items)

    @Slot(result=bool)
    def pick_input_file(self) -> bool:
        """通过文件对话框选择输入文件。"""
        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "选择音频或视频文件",
            "",
            MEDIA_FILE_FILTER,
        )
        return self.set_selected_file(file_path) if file_path else False

    @Slot(str, result=bool)
    def set_selected_file(self, file_path: str) -> bool:
        """设置当前待转录文件。"""
        normalized = normalize_local_path(file_path)
        if not normalized or not ensure_supported_media_file(normalized):
            self._set_error("当前文件类型不受支持")
            return False

        summary = build_file_summary(normalized)
        self.clear_result()
        self._local_state.update(
            {
                "selectedFilePath": normalized,
                "selectedFileName": summary["fileName"],
                "fileSuffix": summary["fileSuffix"],
                "fileSizeText": summary["fileSizeText"],
                "taskStatusText": "文件已就绪，可开始转录",
                "lastError": "",
            }
        )
        self.state_changed.emit()
        return True

    @Slot()
    def clear_selected_file(self) -> None:
        """清空当前输入文件与结果。"""
        self.clear_result()
        self._local_state.update(
            {
                "selectedFilePath": "",
                "selectedFileName": "未选择媒体文件",
                "fileSuffix": "--",
                "fileSizeText": "--",
                "taskStatusText": "请选择媒体文件并加载模型",
                "lastError": "",
            }
        )
        self.state_changed.emit()

    @Slot()
    def load_model(self) -> None:
        """加载共享模型。"""
        self._shared_model_runtime.load_model()

    @Slot()
    def reload_model(self) -> None:
        """重载共享模型。"""
        self._shared_model_runtime.reload_model()

    @Slot()
    def unload_model(self) -> None:
        """卸载共享模型。"""
        self._shared_model_runtime.unload_model()

    @Slot()
    def start_transcription(self) -> None:
        """启动后台转录任务。"""
        if not self._local_state["selectedFilePath"]:
            self._set_error("请先选择媒体文件")
            return
        if not self._shared_model_runtime.state["modelReady"]:
            self._set_error("模型尚未加载，请先加载模型")
            return
        if not self._application_state.begin_operation("语音转录"):
            self._set_error("已有后台任务正在运行，请稍后再试")
            return

        self._local_state["isTranscribing"] = True
        self._local_state["taskStatusText"] = "正在语音转录..."
        self._local_state["lastError"] = ""
        self._cancel_requested = False
        self.state_changed.emit()

        thread = QThreadWithReturn(self._transcribe_worker, thread_name="transcription")
        thread.setParent(self)
        self._task_thread = thread
        thread.add_done_callback(self._on_transcription_completed)
        thread.add_failure_callback(self._on_task_error)
        thread.finished_signal.connect(self._on_task_finished)
        thread.start()

    @Slot(result=bool)
    def cancel_current_task(self) -> bool:
        """取消当前任务，优先取消本页转录任务。"""
        if self._task_thread is not None and self._task_thread.running():
            self._cancel_requested = True
            self._local_state["taskStatusText"] = "正在强制停止当前任务..."
            self._local_state["lastError"] = ""
            self.state_changed.emit()
            return self._task_thread.cancel(force_stop=True)
        return self._shared_model_runtime.cancel_current_task()

    @Slot()
    def shutdown(self) -> None:
        """关闭转录后台任务。"""
        if self._task_thread is not None and self._task_thread.running():
            self._task_thread.cancel(force_stop=True)

    @Slot(result=bool)
    def export_transcript_with_dialog(self) -> bool:
        """通过对话框导出全文文本。"""
        default_path = build_default_export_path(str(self._local_state["selectedFilePath"]), ".txt")
        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "导出转录文本",
            default_path,
            TEXT_FILE_FILTER,
        )
        return self.export_transcript(file_path) if file_path else False

    @Slot(result=bool)
    def export_subtitle_with_dialog(self) -> bool:
        """通过对话框导出字幕。"""
        default_path = build_default_export_path(str(self._local_state["selectedFilePath"]), ".srt")
        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "导出字幕",
            default_path,
            SRT_FILE_FILTER,
        )
        return self.export_subtitle(file_path) if file_path else False

    @Slot(str, result=bool)
    def export_transcript(self, file_path: str) -> bool:
        """导出全文文本到指定路径。"""
        return self._export_text(file_path, str(self._local_state["transcriptText"]))

    @Slot(str, result=bool)
    def export_subtitle(self, file_path: str) -> bool:
        """导出字幕文本到指定路径。"""
        return self._export_text(file_path, str(self._local_state["subtitleText"]))

    @Slot(result=bool)
    def copy_transcript(self) -> bool:
        """复制全文文本。"""
        return self._application_state.copy_text(str(self._local_state["transcriptText"]))

    @Slot(result=bool)
    def copy_subtitle(self) -> bool:
        """复制字幕文本。"""
        return self._application_state.copy_text(str(self._local_state["subtitleText"]))

    @Slot()
    def clear_result(self) -> None:
        """清空当前转录结果。"""
        self._timeline_items = []
        self._raw_timestamp_items = []
        self._local_state.update(
            {
                "language": "--",
                "durationText": "--",
                "subtitleLineCount": 0,
                "timestampCount": 0,
                "transcriptText": "",
                "subtitleText": "",
                "lastError": "",
                "hasResult": False,
            }
        )
        self.timeline_items_changed.emit()
        self.raw_timestamp_items_changed.emit()
        self.state_changed.emit()

    def _build_task_status_text(self, shared_state: Dict[str, Any]) -> str:
        """根据共享状态和局部状态构造任务状态文案。"""
        if self._local_state["isTranscribing"]:
            return str(self._local_state["taskStatusText"])
        if shared_state["isBusy"]:
            return str(shared_state["taskStatusText"])
        if self._local_state["lastError"]:
            return str(self._local_state["lastError"])
        if self._local_state["hasResult"]:
            return "转录完成，可导出结果"
        if self._local_state["selectedFilePath"] and shared_state["modelReady"]:
            return "文件已就绪，可开始转录"
        if self._local_state["selectedFilePath"]:
            return "文件已就绪，等待加载模型"
        if shared_state["modelReady"]:
            return "模型已就绪，请选择媒体文件"
        return "请选择媒体文件并加载模型"

    def _transcribe_worker(self) -> Dict[str, Any]:
        """后台执行转录。"""
        asr_service = self._shared_model_runtime.asr_service
        asr_service.configure_interface(self._settings_store.build_asr_config())
        result = asr_service.transcribe(
            str(self._local_state["selectedFilePath"]),
            return_time_stamps=True,
            show_progress=False,
        )
        if result is None:
            raise RuntimeError("转录失败，未返回结果")

        lines: List[Dict[str, Any]] = []
        subtitle_text = ""
        if result.time_stamps:
            from src.model import BreaklineAlgorithm

            breakline = BreaklineAlgorithm(self._settings_store.build_breakline_config())
            audio_data = asr_service.get_last_audio()
            aggregated = (
                breakline.aggregate_with_audio(
                    result.time_stamps,
                    audio_data.data,
                    audio_data.sample_rate,
                )
                if audio_data is not None
                else breakline.aggregate(result.time_stamps)
            )
            lines = serialize_aggregated_lines(aggregated)
            subtitle_text = breakline.to_srt(aggregated)

        return {
            "language": result.language,
            "durationText": format_duration(result.duration),
            "transcriptText": result.text,
            "subtitleText": subtitle_text,
            "rawTimestampItems": serialize_time_stamps(result.time_stamps),
            "timelineItems": lines,
            "subtitleLineCount": len(lines),
            "timestampCount": len(result.time_stamps or []),
        }

    def _set_error(self, message: str) -> None:
        """设置本页错误状态。"""
        self._local_state["lastError"] = message
        self._local_state["taskStatusText"] = message
        self.state_changed.emit()
        logger.error(message)

    def _on_shared_state_changed(self) -> None:
        """共享模型状态变化时刷新页面。"""
        self.state_changed.emit()

    def _on_transcription_completed(self, payload: object) -> None:
        """接收后台转录结果。"""
        data = dict(payload or {})
        self._timeline_items = list(data.get("timelineItems", []))
        self._raw_timestamp_items = list(data.get("rawTimestampItems", []))
        self._local_state.update(
            {
                "language": data.get("language", "--"),
                "durationText": data.get("durationText", "--"),
                "transcriptText": data.get("transcriptText", ""),
                "subtitleText": data.get("subtitleText", ""),
                "subtitleLineCount": data.get("subtitleLineCount", 0),
                "timestampCount": data.get("timestampCount", 0),
                "taskStatusText": "转录完成，可导出结果",
                "lastError": "",
                "hasResult": True,
            }
        )
        self.timeline_items_changed.emit()
        self.raw_timestamp_items_changed.emit()
        self.state_changed.emit()

    def _on_task_error(self, error: object) -> None:
        """处理后台任务错误。"""
        message = str(error)
        self._local_state["lastError"] = message
        self._local_state["taskStatusText"] = message
        self.state_changed.emit()

    def _on_task_finished(self) -> None:
        """清理转录后台任务。"""
        thread = self._task_thread
        self._task_thread = None
        self._local_state["isTranscribing"] = False
        if self._cancel_requested:
            self._local_state["taskStatusText"] = "任务已强制停止"
            self._local_state["lastError"] = ""
        self._cancel_requested = False
        self._application_state.finish_operation()
        self.state_changed.emit()
        if thread is not None:
            thread.deleteLater()

    def _export_text(self, file_path: str, content: str) -> bool:
        """导出文本到指定文件。"""
        normalized = normalize_local_path(file_path)
        if not normalized or not content:
            return False

        output = Path(normalized)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        logger.success(f"文件已导出: {output}")
        return True
