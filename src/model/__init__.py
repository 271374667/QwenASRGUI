"""模型层导出入口。"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "ASRConfig",
    "ASRInterface",
    "ASRModelHolder",
    "ASRService",
    "AggregatedLine",
    "AlignmentResult",
    "AudioData",
    "BreaklineAlgorithm",
    "BreaklineConfig",
    "GapDetectionMethod",
    "Language",
    "MediaHandler",
    "ModelConfig",
    "ModelSize",
    "ModelStatus",
    "QuantizationMode",
    "SystemHandler",
    "SystemHandlerConfig",
    "TimeStampItem",
    "TranscriptionResult",
]

_MODEL_MODULES = {
    "ASRConfig": "src.model.asr",
    "ASRInterface": "src.model.asr",
    "ASRModelHolder": "src.model.asr",
    "ASRService": "src.model.asr",
    "AggregatedLine": "src.model.value_objects",
    "AlignmentResult": "src.model.value_objects",
    "AudioData": "src.model.media",
    "BreaklineAlgorithm": "src.model.subtitles",
    "BreaklineConfig": "src.model.subtitles",
    "GapDetectionMethod": "src.model.subtitles",
    "Language": "src.model.asr",
    "MediaHandler": "src.model.media",
    "ModelConfig": "src.model.asr",
    "ModelSize": "src.model.asr",
    "ModelStatus": "src.model.asr",
    "QuantizationMode": "src.model.asr",
    "SystemHandler": "src.model.system",
    "SystemHandlerConfig": "src.model.system",
    "TimeStampItem": "src.model.value_objects",
    "TranscriptionResult": "src.model.value_objects",
}


def __getattr__(name: str) -> Any:
    """按需导入模型对象。"""
    module_name = _MODEL_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module 'src.model' has no attribute {name!r}")

    module = import_module(module_name)
    return getattr(module, name)
