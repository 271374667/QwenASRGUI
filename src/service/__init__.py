"""GUI 服务桥接层。"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from qthreadwithreturn import QThreadWithReturn

__all__ = [
    "AlignmentService",
    "ApplicationService",
    "LogService",
    "QThreadWithReturn",
    "SettingsService",
    "TranscriptionService",
]

_SERVICE_MODULES = {
    "AlignmentService": "src.service.alignment_service",
    "ApplicationService": "src.service.application_service",
    "LogService": "src.service.log_service",
    "SettingsService": "src.service.settings_service",
    "TranscriptionService": "src.service.transcription_service",
}


def __getattr__(name: str) -> Any:
    """按需加载服务对象，避免启动时导入重模块。"""
    if name == "QThreadWithReturn":
        return QThreadWithReturn

    module_name = _SERVICE_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module 'src.service' has no attribute {name!r}")

    module = import_module(module_name)
    return getattr(module, name)
