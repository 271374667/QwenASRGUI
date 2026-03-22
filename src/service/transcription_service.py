"""转录页面服务。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFileDialog
from qthreadwithreturn import QThreadWithReturn

from src.service.application_service import ApplicationService
from src.service.service_utils import (
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
from src.service.settings_service import SettingsService


class TranscriptionService(QObject):
    """转录页面的前后端桥接服务。

    该服务负责文件选择、共享模型加载、语音转录、字幕聚合与结果导出，
    并将页面状态与结果转换为 QML 可绑定的数据结构。

    Attributes:
        state_changed: 页面状态变化通知。
        timeline_items_changed: 聚合字幕行变化通知。
        raw_timestamp_items_changed: 原始时间戳变化通知。
    """

    state_changed = Signal()
    timeline_items_changed = Signal()
    raw_timestamp_items_changed = Signal()

    def __init__(
        self,
        application_service: ApplicationService,
        settings_service: SettingsService,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._application_service = application_service
        self._settings_service = settings_service
        self._asr_service = None
        self._asr_signals_connected = False
        self._task_thread: Optional[QThreadWithReturn] = None
        self._cancel_requested = False
        self._timeline_items: List[Dict[str, Any]] = []
        self._raw_timestamp_items: List[Dict[str, Any]] = []
        self._state: Dict[str, Any] = {
            "selectedFilePath": "",
            "selectedFileName": "未选择媒体文件",
            "fileSuffix": "--",
            "fileSizeText": "--",
            "modelReady": False,
            "modelStatusText": "未加载",
            "modelName": "Qwen3-ASR",
            "modelDetails": "共享模型尚未加载",
            "loadingProgress": 0,
            "isBusy": False,
            "isLoadingModel": False,
            "isTranscribing": False,
            "taskStatusText": "请选择媒体文件并加载模型",
            "language": "--",
            "durationText": "--",
            "subtitleLineCount": 0,
            "timestampCount": 0,
            "transcriptText": "",
            "subtitleText": "",
            "lastError": "",
            "hasResult": False,
            "canLoadModel": True,
            "canUnloadModel": False,
            "canReloadModel": False,
            "canStartTranscription": False,
            "canCancelTask": False,
            "canExportTranscript": False,
            "canExportSubtitle": False,
        }
        self._refresh_shared_model_state()

    @Property("QVariantMap", notify=state_changed)
    def state(self) -> Dict[str, Any]:
        return dict(self._state)

    @Property("QVariantList", notify=timeline_items_changed)
    def timeline_items(self) -> List[Dict[str, Any]]:
        return list(self._timeline_items)

    @Property("QVariantList", notify=raw_timestamp_items_changed)
    def raw_timestamp_items(self) -> List[Dict[str, Any]]:
        return list(self._raw_timestamp_items)

    @Slot(result=bool)
    def pick_input_file(self) -> bool:
        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "选择音频或视频文件",
            "",
            MEDIA_FILE_FILTER,
        )
        return self.set_selected_file(file_path) if file_path else False

    @Slot(str, result=bool)
    def set_selected_file(self, file_path: str) -> bool:
        normalized = normalize_local_path(file_path)
        if not normalized or not ensure_supported_media_file(normalized):
            self._set_error("当前文件类型不受支持")
            return False

        summary = build_file_summary(normalized)
        self.clear_result()
        self._state.update(
            {
                "selectedFilePath": normalized,
                "selectedFileName": summary["fileName"],
                "fileSuffix": summary["fileSuffix"],
                "fileSizeText": summary["fileSizeText"],
                "taskStatusText": "文件已就绪，可开始转录",
                "lastError": "",
            }
        )
        self._refresh_shared_model_state()
        return True

    @Slot()
    def clear_selected_file(self) -> None:
        self.clear_result()
        self._state.update(
            {
                "selectedFilePath": "",
                "selectedFileName": "未选择媒体文件",
                "fileSuffix": "--",
                "fileSizeText": "--",
                "taskStatusText": "请选择媒体文件并加载模型",
                "lastError": "",
            }
        )
        self._refresh_shared_model_state()

    @Slot()
    def load_model(self) -> None:
        self._start_background_task(
            "加载共享模型",
            "isLoadingModel",
            self._load_model_worker,
            self._on_model_loaded,
        )

    @Slot()
    def reload_model(self) -> None:
        self._start_background_task(
            "重新加载共享模型",
            "isLoadingModel",
            self._reload_model_worker,
            self._on_model_loaded,
        )

    @Slot()
    def unload_model(self) -> None:
        self._start_background_task(
            "卸载共享模型",
            "",
            self._unload_model_worker,
            self._on_model_unloaded,
        )

    @Slot()
    def start_transcription(self) -> None:
        if not self._state["selectedFilePath"]:
            self._set_error("请先选择媒体文件")
            return
        if not self._asr_service.is_ready:
            self._set_error("模型尚未加载，请先加载模型")
            return

        self._start_background_task(
            "语音转录",
            "isTranscribing",
            self._transcribe_worker,
            self._on_transcription_completed,
        )

    @Slot(result=bool)
    def cancel_current_task(self) -> bool:
        if self._task_thread is None or not self._task_thread.running():
            return False

        self._cancel_requested = True
        self._state["taskStatusText"] = "正在强制停止当前任务..."
        self._state["lastError"] = ""
        self.state_changed.emit()
        return self._task_thread.cancel(force_stop=True)

    @Slot(result=bool)
    def export_transcript_with_dialog(self) -> bool:
        default_path = build_default_export_path(str(self._state["selectedFilePath"]), ".txt")
        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "导出转录文本",
            default_path,
            TEXT_FILE_FILTER,
        )
        return self.export_transcript(file_path) if file_path else False

    @Slot(result=bool)
    def export_subtitle_with_dialog(self) -> bool:
        default_path = build_default_export_path(str(self._state["selectedFilePath"]), ".srt")
        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "导出字幕",
            default_path,
            SRT_FILE_FILTER,
        )
        return self.export_subtitle(file_path) if file_path else False

    @Slot(str, result=bool)
    def export_transcript(self, file_path: str) -> bool:
        return self._export_text(file_path, str(self._state["transcriptText"]))

    @Slot(str, result=bool)
    def export_subtitle(self, file_path: str) -> bool:
        return self._export_text(file_path, str(self._state["subtitleText"]))

    @Slot(result=bool)
    def copy_transcript(self) -> bool:
        return self._copy_text(str(self._state["transcriptText"]))

    @Slot(result=bool)
    def copy_subtitle(self) -> bool:
        return self._copy_text(str(self._state["subtitleText"]))

    @Slot()
    def clear_result(self) -> None:
        self._timeline_items = []
        self._raw_timestamp_items = []
        self._state.update(
            {
                "language": "--",
                "durationText": "--",
                "subtitleLineCount": 0,
                "timestampCount": 0,
                "transcriptText": "",
                "subtitleText": "",
                "hasResult": False,
                "canExportTranscript": False,
                "canExportSubtitle": False,
            }
        )
        self.timeline_items_changed.emit()
        self.raw_timestamp_items_changed.emit()
        self.state_changed.emit()

    def _load_model_worker(self) -> Dict[str, Any]:
        asr_service = self._ensure_asr_service()
        system_config = self._settings_service.build_system_config()
        if system_config.enable_memory_limit:
            from src.common.system_handler import SystemHandler

            SystemHandler(system_config).apply_limits()

        success = asr_service.load_model(self._settings_service.build_model_config())
        if not success:
            raise RuntimeError("模型加载失败")

        asr_service.configure_interface(self._settings_service.build_asr_config())
        return {"success": True}

    def _reload_model_worker(self) -> Dict[str, Any]:
        asr_service = self._ensure_asr_service()
        system_config = self._settings_service.build_system_config()
        if system_config.enable_memory_limit:
            from src.common.system_handler import SystemHandler

            SystemHandler(system_config).apply_limits()

        success = asr_service.reload_model(self._settings_service.build_model_config())
        if not success:
            raise RuntimeError("模型重新加载失败")

        asr_service.configure_interface(self._settings_service.build_asr_config())
        return {"success": True}

    def _unload_model_worker(self) -> Dict[str, Any]:
        self._ensure_asr_service().unload_model()
        return {"success": True}

    def _transcribe_worker(self) -> Dict[str, Any]:
        asr_service = self._ensure_asr_service()
        asr_service.configure_interface(self._settings_service.build_asr_config())
        result = asr_service.transcribe(
            str(self._state["selectedFilePath"]),
            return_time_stamps=True,
            show_progress=False,
        )
        if result is None:
            raise RuntimeError("转录失败，未返回结果")

        lines: List[Dict[str, Any]] = []
        subtitle_text = ""
        if result.time_stamps:
            from src.common.breakline_algorithm import BreaklineAlgorithm

            breakline = BreaklineAlgorithm(self._settings_service.build_breakline_config())
            audio_data = asr_service.get_last_audio()
            aggregated = (
                breakline.aggregate_with_audio(result.time_stamps, audio_data.data, audio_data.sample_rate)
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

    def _start_background_task(
        self,
        operation_name: str,
        busy_flag_name: str,
        worker: Any,
        result_handler: Any,
    ) -> None:
        if not self._application_service.begin_operation(operation_name):
            self._set_error("已有后台任务正在运行，请稍后再试")
            return

        self._state["isBusy"] = True
        self._cancel_requested = False
        if busy_flag_name:
            self._state[busy_flag_name] = True
        self._state["taskStatusText"] = f"正在{operation_name}..."
        self._state["lastError"] = ""
        self.state_changed.emit()

        thread = QThreadWithReturn(worker, thread_name=operation_name)
        thread.setParent(self)
        self._task_thread = thread
        thread.add_done_callback(result_handler)
        thread.add_failure_callback(self._on_task_error)
        thread.finished_signal.connect(self._on_task_finished)
        thread.start()

    def _refresh_shared_model_state(self) -> None:
        if self._asr_service is None:
            model_ready = False
            model_status_text = "未加载"
            model_name = "Qwen3-ASR"
            quantization = "auto"
        else:
            model_ready = self._asr_service.is_ready
            model_status_text = self._asr_service.status.value
            model_name = self._asr_service.model_name
            quantization = (
                self._asr_service.actual_quantization_mode.value
                if self._asr_service.actual_quantization_mode is not None
                else "auto"
            )

        self._state.update(
            {
                "modelReady": model_ready,
                "modelStatusText": model_status_text,
                "modelName": model_name,
                "modelDetails": f"量化模式: {quantization}" if model_ready else "共享模型尚未加载",
                "canLoadModel": (not model_ready) and not self._state["isBusy"],
                "canUnloadModel": model_ready and not self._state["isBusy"],
                "canReloadModel": model_ready and not self._state["isBusy"],
                "canStartTranscription": bool(self._state["selectedFilePath"]) and model_ready and not self._state["isBusy"],
                "canCancelTask": self._state["isBusy"],
            }
        )
        self.state_changed.emit()

    def _set_error(self, message: str) -> None:
        self._state["lastError"] = message
        self._state["taskStatusText"] = message
        self.state_changed.emit()
        logger.error(message)

    def _on_shared_status_changed(self, _status: object) -> None:
        self._refresh_shared_model_state()

    def _on_loading_progress(self, value: int) -> None:
        self._state["loadingProgress"] = value
        self.state_changed.emit()

    def _on_model_loaded(self, _result: object) -> None:
        self._state["taskStatusText"] = "模型已就绪，可开始转录"
        self._state["lastError"] = ""
        self._refresh_shared_model_state()

    def _on_model_unloaded(self, _result: object) -> None:
        self._state["loadingProgress"] = 0
        self._state["taskStatusText"] = "模型已卸载"
        self._state["lastError"] = ""
        self._refresh_shared_model_state()

    def _on_transcription_completed(self, payload: object) -> None:
        data = dict(payload or {})
        self._timeline_items = list(data.get("timelineItems", []))
        self._raw_timestamp_items = list(data.get("rawTimestampItems", []))
        self._state.update(
            {
                "language": data.get("language", "--"),
                "durationText": data.get("durationText", "--"),
                "transcriptText": data.get("transcriptText", ""),
                "subtitleText": data.get("subtitleText", ""),
                "subtitleLineCount": data.get("subtitleLineCount", 0),
                "timestampCount": data.get("timestampCount", 0),
                "hasResult": True,
                "canExportTranscript": bool(data.get("transcriptText")),
                "canExportSubtitle": bool(data.get("subtitleText")),
                "taskStatusText": "转录完成，可导出结果",
                "lastError": "",
            }
        )
        self.timeline_items_changed.emit()
        self.raw_timestamp_items_changed.emit()
        self.state_changed.emit()

    def _on_task_error(self, error: object) -> None:
        message = str(error)
        self._state["lastError"] = message
        self._state["taskStatusText"] = message
        self.state_changed.emit()

    def _on_task_finished(self) -> None:
        thread = self._task_thread
        self._task_thread = None
        self._state["isBusy"] = False
        self._state["isLoadingModel"] = False
        self._state["isTranscribing"] = False
        if self._cancel_requested:
            self._state["taskStatusText"] = "任务已强制停止"
            self._state["lastError"] = ""
        self._cancel_requested = False
        if self._asr_service is None or not self._asr_service.is_ready:
            self._state["loadingProgress"] = 0
        self._application_service.finish_operation()
        self._refresh_shared_model_state()
        if thread is not None:
            thread.deleteLater()

    def _ensure_asr_service(self):
        """按需创建并连接共享 ASR 服务。"""
        if self._asr_service is None:
            from src.common.asr import ASRService

            self._asr_service = ASRService()

        if not self._asr_signals_connected:
            self._asr_service.signals.status_changed.connect(self._on_shared_status_changed)
            self._asr_service.signals.loading_progress.connect(self._on_loading_progress)
            self._asr_signals_connected = True

        return self._asr_service

    def _copy_text(self, text: str) -> bool:
        if not text:
            return False
        QGuiApplication.clipboard().setText(text)
        return True

    def _export_text(self, file_path: str, content: str) -> bool:
        normalized = normalize_local_path(file_path)
        if not normalized or not content:
            return False
        output = Path(normalized)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        logger.success(f"文件已导出: {output}")
        return True
