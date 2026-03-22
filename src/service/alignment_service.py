"""对齐页面服务。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFileDialog
from qthreadwithreturn import QThreadWithReturn

from src.common.asr import ASRService, Language
from src.common.breakline_algorithm import BreaklineAlgorithm
from src.service.application_service import ApplicationService
from src.service.service_utils import (
    MEDIA_FILE_FILTER,
    SRT_FILE_FILTER,
    build_default_export_path,
    build_file_summary,
    ensure_supported_media_file,
    format_duration,
    normalize_local_path,
    serialize_aggregated_lines,
    serialize_time_stamps,
)
from src.service.settings_service import SettingsService


class AlignmentService(QObject):
    """强制对齐页面的桥接服务。

    该服务负责接收用户输入的音频与文本，调用共享 ASR 模型执行强制对齐，
    并将对齐后的时间戳、字幕行和导出文本暴露给 QML 页面。

    Attributes:
        state_changed: 页面状态变化通知。
        line_items_changed: 聚合字幕行变化通知。
        word_items_changed: 原始对齐时间戳变化通知。
        language_options_changed: 语言选项变化通知。
    """

    state_changed = Signal()
    line_items_changed = Signal()
    word_items_changed = Signal()
    language_options_changed = Signal()

    def __init__(
        self,
        application_service: ApplicationService,
        settings_service: SettingsService,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._application_service = application_service
        self._settings_service = settings_service
        self._asr_service = ASRService()
        self._task_thread: Optional[QThreadWithReturn] = None
        self._cancel_requested = False
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
        self._state: Dict[str, Any] = {
            "selectedFilePath": "",
            "selectedFileName": "未选择音频文件",
            "fileSuffix": "--",
            "fileSizeText": "--",
            "inputText": "",
            "selectedLanguage": "Chinese",
            "modelReady": False,
            "modelStatusText": "未加载",
            "modelName": "Qwen3-ASR",
            "isBusy": False,
            "isAligning": False,
            "taskStatusText": "请选择音频并输入待对齐文本",
            "audioDurationText": "--",
            "wordCount": 0,
            "lineCount": 0,
            "subtitleText": "",
            "rawTimestampText": "",
            "lastError": "",
            "hasResult": False,
            "canStartAlignment": False,
            "canCancelTask": False,
            "canExportSubtitle": False,
        }
        self._asr_service.signals.status_changed.connect(self._on_shared_status_changed)
        self._refresh_shared_model_state()

    @Property("QVariantMap", notify=state_changed)
    def state(self) -> Dict[str, Any]:
        return dict(self._state)

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
        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "选择对齐音频",
            "",
            MEDIA_FILE_FILTER,
        )
        return self.set_selected_file(file_path) if file_path else False

    @Slot(str, result=bool)
    def set_selected_file(self, file_path: str) -> bool:
        normalized = normalize_local_path(file_path)
        if not normalized or not ensure_supported_media_file(normalized):
            self._set_error("请选择受支持的音频或视频文件")
            return False

        summary = build_file_summary(normalized)
        self.clear_result()
        self._state.update(
            {
                "selectedFilePath": normalized,
                "selectedFileName": summary["fileName"],
                "fileSuffix": summary["fileSuffix"],
                "fileSizeText": summary["fileSizeText"],
                "taskStatusText": "音频已就绪，可开始对齐",
                "lastError": "",
            }
        )
        self._refresh_shared_model_state()
        return True

    @Slot(str)
    def update_input_text(self, text: str) -> None:
        self._state["inputText"] = text
        self._refresh_shared_model_state()

    @Slot(str)
    def update_language(self, language_value: str) -> None:
        self._state["selectedLanguage"] = language_value
        self.state_changed.emit()

    @Slot()
    def start_alignment(self) -> None:
        if not self._state["selectedFilePath"]:
            self._set_error("请先选择音频文件")
            return
        if not str(self._state["inputText"]).strip():
            self._set_error("请输入待对齐文本")
            return
        if not self._asr_service.is_ready:
            self._set_error("共享模型尚未加载，请先在转录页加载模型")
            return

        if not self._application_service.begin_operation("强制对齐"):
            self._set_error("已有后台任务正在运行，请稍后再试")
            return

        self._state["isBusy"] = True
        self._state["isAligning"] = True
        self._cancel_requested = False
        self._state["taskStatusText"] = "正在执行强制对齐..."
        self._state["lastError"] = ""
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
        if self._task_thread is None or not self._task_thread.running():
            return False

        self._cancel_requested = True
        self._state["taskStatusText"] = "正在强制停止当前任务..."
        self._state["lastError"] = ""
        self.state_changed.emit()
        return self._task_thread.cancel(force_stop=True)

    @Slot(result=bool)
    def export_subtitle_with_dialog(self) -> bool:
        default_path = build_default_export_path(str(self._state["selectedFilePath"]), ".srt")
        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "导出对齐字幕",
            default_path,
            SRT_FILE_FILTER,
        )
        return self.export_subtitle(file_path) if file_path else False

    @Slot(str, result=bool)
    def export_subtitle(self, file_path: str) -> bool:
        normalized = normalize_local_path(file_path)
        if not normalized or not self._state["subtitleText"]:
            return False

        output = Path(normalized)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(str(self._state["subtitleText"]), encoding="utf-8")
        logger.success(f"对齐字幕已导出: {output}")
        return True

    @Slot(result=bool)
    def copy_subtitle(self) -> bool:
        return self._copy_text(str(self._state["subtitleText"]))

    @Slot(result=bool)
    def copy_raw_timestamps(self) -> bool:
        return self._copy_text(str(self._state["rawTimestampText"]))

    @Slot()
    def clear_result(self) -> None:
        self._line_items = []
        self._word_items = []
        self._state.update(
            {
                "audioDurationText": "--",
                "wordCount": 0,
                "lineCount": 0,
                "subtitleText": "",
                "rawTimestampText": "",
                "hasResult": False,
                "canExportSubtitle": False,
            }
        )
        self.line_items_changed.emit()
        self.word_items_changed.emit()
        self.state_changed.emit()

    def _align_worker(self) -> Dict[str, Any]:
        self._asr_service.configure_interface(self._settings_service.build_asr_config())
        result = self._asr_service.align(
            str(self._state["selectedFilePath"]),
            str(self._state["inputText"]),
            self._map_language(str(self._state["selectedLanguage"])),
        )

        breakline = BreaklineAlgorithm(self._settings_service.build_breakline_config())
        audio_data = self._asr_service.get_last_audio()
        aggregated = (
            breakline.aggregate_with_audio(result.time_stamps, audio_data.data, audio_data.sample_rate)
            if audio_data is not None
            else breakline.aggregate(result.time_stamps)
        )
        raw_items = serialize_time_stamps(result.time_stamps)
        raw_text = "\n".join(
            f"{item['startLabel']} - {item['endLabel']}  {item['text']}"
            for item in raw_items
        )

        return {
            "audioDurationText": format_duration(result.audio_duration),
            "wordCount": len(result.time_stamps),
            "lineCount": len(aggregated),
            "subtitleText": breakline.to_srt(aggregated),
            "rawTimestampText": raw_text,
            "lineItems": serialize_aggregated_lines(aggregated),
            "wordItems": raw_items,
        }

    def _refresh_shared_model_state(self) -> None:
        model_ready = self._asr_service.is_ready
        self._state.update(
            {
                "modelReady": model_ready,
                "modelStatusText": self._asr_service.status.value,
                "modelName": self._asr_service.model_name,
                "canStartAlignment": bool(self._state["selectedFilePath"]) and bool(str(self._state["inputText"]).strip()) and model_ready and not self._state["isBusy"],
                "canCancelTask": self._state["isBusy"],
            }
        )
        self.state_changed.emit()

    def _map_language(self, language_value: str) -> Language:
        for language in Language:
            if language.value == language_value:
                return language
        return Language.CHINESE

    def _set_error(self, message: str) -> None:
        self._state["lastError"] = message
        self._state["taskStatusText"] = message
        self.state_changed.emit()
        logger.error(message)

    def _on_shared_status_changed(self, _status: object) -> None:
        self._refresh_shared_model_state()

    def _on_alignment_completed(self, payload: object) -> None:
        data = dict(payload or {})
        self._line_items = list(data.get("lineItems", []))
        self._word_items = list(data.get("wordItems", []))
        self._state.update(
            {
                "audioDurationText": data.get("audioDurationText", "--"),
                "wordCount": data.get("wordCount", 0),
                "lineCount": data.get("lineCount", 0),
                "subtitleText": data.get("subtitleText", ""),
                "rawTimestampText": data.get("rawTimestampText", ""),
                "hasResult": True,
                "canExportSubtitle": bool(data.get("subtitleText")),
                "taskStatusText": "对齐完成，可导出字幕",
                "lastError": "",
            }
        )
        self.line_items_changed.emit()
        self.word_items_changed.emit()
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
        self._state["isAligning"] = False
        if self._cancel_requested:
            self._state["taskStatusText"] = "任务已强制停止"
            self._state["lastError"] = ""
        self._cancel_requested = False
        self._application_service.finish_operation()
        self._refresh_shared_model_state()
        if thread is not None:
            thread.deleteLater()

    def _copy_text(self, text: str) -> bool:
        if not text:
            return False
        QGuiApplication.clipboard().setText(text)
        return True
