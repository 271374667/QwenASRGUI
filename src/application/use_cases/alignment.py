"""强制对齐用例。"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from src.application.file_support import (
    format_duration,
    serialize_aggregated_lines,
    serialize_time_stamps,
)
from src.application.settings_store import SettingsStore
from src.application.shared_model_runtime import SharedModelRuntime


class AlignmentUseCase:
    """执行强制对齐并返回页面可消费的数据。"""

    def __init__(
        self,
        settings_store: SettingsStore,
        shared_model_runtime: SharedModelRuntime,
    ) -> None:
        """初始化强制对齐用例。"""
        self._settings_store = settings_store
        self._shared_model_runtime = shared_model_runtime

    def execute(
        self,
        selected_file_path: str,
        input_text: str,
        selected_language: str,
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
    ) -> Dict[str, Any]:
        """执行强制对齐。"""
        asr_service = self._shared_model_runtime.asr_service
        asr_service.configure_interface(self._settings_store.build_asr_config())
        self._notify_progress(
            progress_callback,
            4,
            100,
            "准备开始对齐...",
            "正在初始化对齐参数",
        )
        result = asr_service.align(
            selected_file_path,
            input_text,
            self._map_language(selected_language),
            progress_callback=progress_callback,
        )

        from src.model import BreaklineAlgorithm

        self._notify_progress(
            progress_callback,
            90,
            100,
            "正在整理字幕与时间戳...",
            f"正在处理 {len(result.time_stamps)} 个词级时间戳",
        )
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
        self._notify_progress(
            progress_callback,
            100,
            100,
            "对齐结果整理完成",
            f"共生成 {len(aggregated)} 条字幕",
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

    def _notify_progress(
        self,
        callback: Optional[Callable[[int, int, str, str], None]],
        value: int,
        maximum: int,
        status_text: str,
        detail_text: str,
    ) -> None:
        """在存在回调时转发对齐进度。"""
        if callback is None:
            return
        callback(value, maximum, status_text, detail_text)
