"""转录用例。"""

from __future__ import annotations

from typing import Any, Dict, List

from src.application.file_support import (
    format_duration,
    serialize_aggregated_lines,
    serialize_time_stamps,
)
from src.application.settings_store import SettingsStore
from src.application.shared_model_runtime import SharedModelRuntime


class TranscriptionUseCase:
    """执行媒体转录并返回页面可消费的数据。"""

    def __init__(
        self,
        settings_store: SettingsStore,
        shared_model_runtime: SharedModelRuntime,
    ) -> None:
        """初始化转录用例。"""
        self._settings_store = settings_store
        self._shared_model_runtime = shared_model_runtime

    def execute(self, selected_file_path: str) -> Dict[str, Any]:
        """执行转录。"""
        asr_service = self._shared_model_runtime.asr_service
        asr_service.configure_interface(self._settings_store.build_asr_config())
        result = asr_service.transcribe(
            selected_file_path,
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
