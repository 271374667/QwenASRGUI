"""QML 页面使用的 ViewModel 导出入口。"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "AlignmentViewModel",
    "LogViewModel",
    "SettingsViewModel",
    "TranscriptionViewModel",
]

_VIEWMODEL_MODULES = {
    "AlignmentViewModel": "src.viewmodel.alignment_viewmodel",
    "LogViewModel": "src.viewmodel.log_viewmodel",
    "SettingsViewModel": "src.viewmodel.settings_viewmodel",
    "TranscriptionViewModel": "src.viewmodel.transcription_viewmodel",
}


def __getattr__(name: str) -> Any:
    """按需加载 ViewModel，避免启动时导入非必要模块。"""
    module_name = _VIEWMODEL_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module 'src.viewmodel' has no attribute {name!r}")

    module = import_module(module_name)
    return getattr(module, name)
