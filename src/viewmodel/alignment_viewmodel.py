"""对齐页 ViewModel。"""

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


class AlignmentViewModel(QObject):
    """管理强制对齐页的状态和交互。

    该 ViewModel 负责组织音频选择、文本输入、语言选择和对齐结果，
    并通过 `SharedModelRuntime` 复用共享模型状态与模型操作能力。

    Attributes:
        state_changed: 页面状态变化通知。
        line_items_changed: 字幕行变化通知。
        word_items_changed: 词级时间戳变化通知。
        language_options_changed: 语言选项变化通知。

    Example:
        基本用法示例::

            view_model = AlignmentViewModel(app_state, settings_store, shared_model_runtime)
            view_model.update_input_text("你好，世界")
            view_model.start_alignment()

    Note:
        对齐页不会直接访问设置服务或共享模型服务，所有交互都通过当前 ViewModel 对外暴露。
    """

    state_changed = Signal()
    line_items_changed = Signal()
    word_items_changed = Signal()
    language_options_changed = Signal()

    def __init__(
        self,
        application_state: ApplicationState,
        settings_store: SettingsStore,
        shared_model_runtime: SharedModelRuntime,
        parent: Optional[QObject] = None,
    ) -> None:
        """初始化对齐页 ViewModel。"""
        super().__init__(parent)
        self._application_state = application_state
        self._settings_store = settings_store
        self._shared_model_runtime = shared_model_runtime
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
        self._local_state: Dict[str, Any] = {
            "selectedFilePath": "",
            "selectedFileName": "未选择音频文件",
            "fileSuffix": "--",
            "fileSizeText": "--",
            "inputText": "",
            "selectedLanguage": "Chinese",
            "isAligning": False,
            "taskStatusText": "请选择音频并输入待对齐文本",
            "audioDurationText": "--",
            "wordCount": 0,
            "lineCount": 0,
            "subtitleText": "",
            "rawTimestampText": "",
            "lastError": "",
            "hasResult": False,
        }
        self._shared_model_runtime.state_changed.connect(self._on_shared_state_changed)

    @Property("QVariantMap", notify=state_changed)
    def state(self) -> Dict[str, Any]:
        """返回供 QML 绑定的页面状态。"""
        shared_state = self._shared_model_runtime.state
        app_busy = bool(self._application_state.state["isBusy"])
        page_busy = bool(self._local_state["isAligning"])
        is_busy = page_busy or bool(shared_state["isBusy"])
        model_ready = bool(shared_state["modelReady"])
        last_error = str(self._local_state["lastError"] or shared_state["lastError"])
        return {
            "selectedFilePath": self._local_state["selectedFilePath"],
            "selectedFileName": self._local_state["selectedFileName"],
            "fileSuffix": self._local_state["fileSuffix"],
            "fileSizeText": self._local_state["fileSizeText"],
            "inputText": self._local_state["inputText"],
            "selectedLanguage": self._local_state["selectedLanguage"],
            "modelReady": model_ready,
            "modelStatusText": shared_state["modelStatusText"],
            "modelName": shared_state["modelName"],
            "modelDetails": shared_state["modelDetails"],
            "isBusy": is_busy,
            "isAligning": page_busy,
            "taskStatusText": self._build_task_status_text(shared_state),
            "audioDurationText": self._local_state["audioDurationText"],
            "wordCount": self._local_state["wordCount"],
            "lineCount": self._local_state["lineCount"],
            "subtitleText": self._local_state["subtitleText"],
            "rawTimestampText": self._local_state["rawTimestampText"],
            "lastError": last_error,
            "hasResult": self._local_state["hasResult"],
            "canLoadModel": shared_state["canLoadModel"],
            "canReloadModel": shared_state["canReloadModel"],
            "canStartAlignment": (
                bool(self._local_state["selectedFilePath"])
                and bool(str(self._local_state["inputText"]).strip())
                and model_ready
                and (not page_busy)
                and (not app_busy)
            ),
            "canCancelTask": page_busy or bool(shared_state["canCancelTask"]),
            "canExportSubtitle": bool(self._local_state["subtitleText"]) and (not is_busy),
        }

    @Property("QVariantList", notify=language_options_changed)
    def language_options(self) -> List[Dict[str, str]]:
        """返回语言选项。"""
        return list(self._language_options)

    @Property("QVariantList", notify=line_items_changed)
    def line_items(self) -> List[Dict[str, Any]]:
        """返回聚合字幕行。"""
        return list(self._line_items)

    @Property("QVariantList", notify=word_items_changed)
    def word_items(self) -> List[Dict[str, Any]]:
        """返回词级时间戳。"""
        return list(self._word_items)

    @Slot(result=bool)
    def pick_input_file(self) -> bool:
        """通过文件对话框选择对齐音频。"""
        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "选择对齐音频",
            "",
            MEDIA_FILE_FILTER,
        )
        return self.set_selected_file(file_path) if file_path else False

    @Slot(str, result=bool)
    def set_selected_file(self, file_path: str) -> bool:
        """设置当前待对齐音频。"""
        normalized = normalize_local_path(file_path)
        if not normalized or not ensure_supported_media_file(normalized):
            self._set_error("请选择受支持的音频或视频文件")
            return False

        summary = build_file_summary(normalized)
        self.clear_result()
        self._local_state.update(
            {
                "selectedFilePath": normalized,
                "selectedFileName": summary["fileName"],
                "fileSuffix": summary["fileSuffix"],
                "fileSizeText": summary["fileSizeText"],
                "taskStatusText": "音频已就绪，可开始对齐",
                "lastError": "",
            }
        )
        self.state_changed.emit()
        return True

    @Slot(str)
    def update_input_text(self, text: str) -> None:
        """更新待对齐文本。"""
        self._local_state["inputText"] = text
        self._local_state["lastError"] = ""
        self.state_changed.emit()

    @Slot(str)
    def update_language(self, language_value: str) -> None:
        """更新对齐语言。"""
        self._local_state["selectedLanguage"] = language_value
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
    def start_alignment(self) -> None:
        """启动后台对齐任务。"""
        if not self._local_state["selectedFilePath"]:
            self._set_error("请先选择音频文件")
            return
        if not str(self._local_state["inputText"]).strip():
            self._set_error("请输入待对齐文本")
            return
        if not self._shared_model_runtime.state["modelReady"]:
            self._set_error("共享模型尚未加载，请先加载模型")
            return
        if not self._application_state.begin_operation("强制对齐"):
            self._set_error("已有后台任务正在运行，请稍后再试")
            return

        self._local_state["isAligning"] = True
        self._local_state["taskStatusText"] = "正在执行强制对齐..."
        self._local_state["lastError"] = ""
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
        """取消当前任务，优先取消本页对齐任务。"""
        if self._task_thread is not None and self._task_thread.running():
            self._cancel_requested = True
            self._local_state["taskStatusText"] = "正在强制停止当前任务..."
            self._local_state["lastError"] = ""
            self.state_changed.emit()
            return self._task_thread.cancel(force_stop=True)
        return self._shared_model_runtime.cancel_current_task()

    @Slot()
    def shutdown(self) -> None:
        """关闭对齐后台任务。"""
        if self._task_thread is not None and self._task_thread.running():
            self._task_thread.cancel(force_stop=True)

    @Slot(result=bool)
    def export_subtitle_with_dialog(self) -> bool:
        """通过对话框导出字幕。"""
        default_path = build_default_export_path(str(self._local_state["selectedFilePath"]), ".srt")
        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "导出对齐字幕",
            default_path,
            SRT_FILE_FILTER,
        )
        return self.export_subtitle(file_path) if file_path else False

    @Slot(str, result=bool)
    def export_subtitle(self, file_path: str) -> bool:
        """导出对齐字幕。"""
        normalized = normalize_local_path(file_path)
        if not normalized or not self._local_state["subtitleText"]:
            return False

        output = Path(normalized)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(str(self._local_state["subtitleText"]), encoding="utf-8")
        logger.success(f"对齐字幕已导出: {output}")
        return True

    @Slot(result=bool)
    def copy_subtitle(self) -> bool:
        """复制字幕文本。"""
        return self._application_state.copy_text(str(self._local_state["subtitleText"]))

    @Slot(result=bool)
    def copy_raw_timestamps(self) -> bool:
        """复制原始时间戳文本。"""
        return self._application_state.copy_text(str(self._local_state["rawTimestampText"]))

    @Slot()
    def clear_result(self) -> None:
        """清空当前对齐结果。"""
        self._line_items = []
        self._word_items = []
        self._local_state.update(
            {
                "audioDurationText": "--",
                "wordCount": 0,
                "lineCount": 0,
                "subtitleText": "",
                "rawTimestampText": "",
                "lastError": "",
                "hasResult": False,
            }
        )
        self.line_items_changed.emit()
        self.word_items_changed.emit()
        self.state_changed.emit()

    def _build_task_status_text(self, shared_state: Dict[str, Any]) -> str:
        """根据共享状态和局部状态构造任务文案。"""
        if self._local_state["isAligning"]:
            return str(self._local_state["taskStatusText"])
        if shared_state["isBusy"]:
            return str(shared_state["taskStatusText"])
        if self._local_state["lastError"]:
            return str(self._local_state["lastError"])
        if self._local_state["hasResult"]:
            return "对齐完成，可导出字幕"
        if (
            self._local_state["selectedFilePath"]
            and str(self._local_state["inputText"]).strip()
            and shared_state["modelReady"]
        ):
            return "音频与文本已就绪，可开始对齐"
        if self._local_state["selectedFilePath"] and str(self._local_state["inputText"]).strip():
            return "音频与文本已就绪，等待模型加载"
        return "请选择音频并输入待对齐文本"

    def _align_worker(self) -> Dict[str, Any]:
        """后台执行强制对齐。"""
        asr_service = self._shared_model_runtime.asr_service
        asr_service.configure_interface(self._settings_store.build_asr_config())
        result = asr_service.align(
            str(self._local_state["selectedFilePath"]),
            str(self._local_state["inputText"]),
            self._map_language(str(self._local_state["selectedLanguage"])),
        )

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

    def _map_language(self, language_value: str):
        """将字符串语言映射到枚举值。"""
        from src.model import Language

        for language in Language:
            if language.value == language_value:
                return language
        return Language.CHINESE

    def _set_error(self, message: str) -> None:
        """设置本页错误状态。"""
        self._local_state["lastError"] = message
        self._local_state["taskStatusText"] = message
        self.state_changed.emit()
        logger.error(message)

    def _on_shared_state_changed(self) -> None:
        """共享模型状态变化时刷新页面。"""
        self.state_changed.emit()

    def _on_alignment_completed(self, payload: object) -> None:
        """接收后台对齐结果。"""
        data = dict(payload or {})
        self._line_items = list(data.get("lineItems", []))
        self._word_items = list(data.get("wordItems", []))
        self._local_state.update(
            {
                "audioDurationText": data.get("audioDurationText", "--"),
                "wordCount": data.get("wordCount", 0),
                "lineCount": data.get("lineCount", 0),
                "subtitleText": data.get("subtitleText", ""),
                "rawTimestampText": data.get("rawTimestampText", ""),
                "taskStatusText": "对齐完成，可导出字幕",
                "lastError": "",
                "hasResult": True,
            }
        )
        self.line_items_changed.emit()
        self.word_items_changed.emit()
        self.state_changed.emit()

    def _on_task_error(self, error: object) -> None:
        """处理后台任务错误。"""
        message = str(error)
        self._local_state["lastError"] = message
        self._local_state["taskStatusText"] = message
        self.state_changed.emit()

    def _on_task_finished(self) -> None:
        """清理后台对齐任务。"""
        thread = self._task_thread
        self._task_thread = None
        self._local_state["isAligning"] = False
        if self._cancel_requested:
            self._local_state["taskStatusText"] = "任务已强制停止"
            self._local_state["lastError"] = ""
        self._cancel_requested = False
        self._application_state.finish_operation()
        self.state_changed.emit()
        if thread is not None:
            thread.deleteLater()
