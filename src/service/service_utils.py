"""GUI 服务层辅助函数。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QUrl

from src.core.vo import AggregatedLine, TimeStampItem

AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv"}

MEDIA_FILE_FILTER = (
    "媒体文件 (*.mp3 *.wav *.flac *.ogg *.m4a *.aac *.wma *.mp4 *.mkv *.mov *.avi *.webm *.flv *.wmv);;"
    "音频文件 (*.mp3 *.wav *.flac *.ogg *.m4a *.aac *.wma);;"
    "视频文件 (*.mp4 *.mkv *.mov *.avi *.webm *.flv *.wmv);;"
    "全部文件 (*.*)"
)
TEXT_FILE_FILTER = "文本文件 (*.txt);;全部文件 (*.*)"
SRT_FILE_FILTER = "SRT 字幕 (*.srt);;全部文件 (*.*)"
LOG_FILE_FILTER = "日志文件 (*.log *.txt);;全部文件 (*.*)"


def normalize_local_path(value: str) -> str:
    """将 QML 传来的 URL 或路径标准化为本地文件路径。"""
    text = str(value or "").strip()
    if not text:
        return ""

    if text.startswith("file:"):
        return QUrl(text).toLocalFile()

    return str(Path(text).expanduser())


def ensure_supported_media_file(path: str) -> bool:
    """检查路径是否为支持的媒体文件。"""
    suffix = Path(path).suffix.lower()
    return suffix in AUDIO_EXTENSIONS or suffix in VIDEO_EXTENSIONS


def format_duration(seconds: float) -> str:
    """格式化秒数为可读时长。"""
    if seconds <= 0:
        return "--"

    total_seconds = int(round(seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_timestamp(seconds: float) -> str:
    """格式化秒数为字幕时间戳。"""
    total_milliseconds = max(0, int(seconds * 1000))
    hours = total_milliseconds // 3_600_000
    minutes = (total_milliseconds % 3_600_000) // 60_000
    secs = (total_milliseconds % 60_000) // 1_000
    milliseconds = total_milliseconds % 1_000
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


def format_file_size(size_bytes: int) -> str:
    """将字节数格式化为可读文本。"""
    if size_bytes <= 0:
        return "--"

    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)

    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024

    return "--"


def build_file_summary(path: str) -> Dict[str, str]:
    """构建文件摘要信息。"""
    file_path = Path(path)
    size_text = "--"

    if file_path.exists():
        size_text = format_file_size(file_path.stat().st_size)

    return {
        "fileName": file_path.name or "未选择文件",
        "filePath": str(file_path),
        "fileSuffix": file_path.suffix.lower() or "--",
        "fileSizeText": size_text,
    }


def serialize_time_stamps(
    time_stamps: Optional[List[TimeStampItem]],
) -> List[Dict[str, Any]]:
    """序列化词级时间戳数据供 QML 使用。"""
    if not time_stamps:
        return []

    items: List[Dict[str, Any]] = []
    for index, item in enumerate(time_stamps, start=1):
        items.append(
            {
                "index": index,
                "text": item.text,
                "startTime": item.start_time,
                "endTime": item.end_time,
                "duration": item.duration,
                "startLabel": format_timestamp(item.start_time),
                "endLabel": format_timestamp(item.end_time),
                "durationLabel": format_duration(item.duration),
            }
        )
    return items


def serialize_aggregated_lines(lines: List[AggregatedLine]) -> List[Dict[str, Any]]:
    """序列化聚合后的字幕行数据供 QML 使用。"""
    items: List[Dict[str, Any]] = []
    for index, item in enumerate(lines, start=1):
        items.append(
            {
                "index": index,
                "text": item.text,
                "startTime": item.start_time,
                "endTime": item.end_time,
                "duration": item.duration,
                "wordCount": item.word_count,
                "startLabel": format_timestamp(item.start_time),
                "endLabel": format_timestamp(item.end_time),
                "durationLabel": format_duration(item.duration),
            }
        )
    return items


def build_default_export_path(source_path: str, suffix: str) -> str:
    """根据源文件推导导出路径。"""
    source = Path(source_path)
    if not source.name:
        return ""
    return str(source.with_suffix(suffix))
