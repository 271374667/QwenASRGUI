"""应用层导出入口。"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "ApplicationState",
    "CompositionRoot",
    "LogStore",
    "SettingsStore",
    "SharedModelRuntime",
]

_APPLICATION_MODULES = {
    "ApplicationState": "src.application.app_state",
    "CompositionRoot": "src.application.composition_root",
    "LogStore": "src.application.log_store",
    "SettingsStore": "src.application.settings_store",
    "SharedModelRuntime": "src.application.shared_model_runtime",
}


def __getattr__(name: str) -> Any:
    """按需导入应用层对象。"""
    module_name = _APPLICATION_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module 'src.application' has no attribute {name!r}")

    module = import_module(module_name)
    return getattr(module, name)
