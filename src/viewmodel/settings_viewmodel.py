"""设置页 ViewModel。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, Property, Signal, Slot

from src.application.app_state import ApplicationState
from src.application.settings_store import SettingsStore
from src.application.shared_model_runtime import SharedModelRuntime


class SettingsViewModel(QObject):
    """管理设置页的展示状态和交互命令。

    该 ViewModel 负责聚合设置服务、应用服务和共享模型服务的数据，
    使设置页只依赖一个 ViewModel 即可完成配置编辑和模型重载。

    Attributes:
        state_changed: 页面状态变化通知。
        settings_changed: 设置数据变化通知。
        options_changed: 下拉选项变化通知。

    Example:
        基本用法示例::

            view_model = SettingsViewModel(app_state, settings_store, shared_model_runtime)
            view_model.update_setting("modelSize", "large")

    Note:
        所有设置持久化仍由 `SettingsStore` 负责，ViewModel 只负责组织界面交互。
    """

    state_changed = Signal()
    settings_changed = Signal()
    options_changed = Signal()

    def __init__(
        self,
        application_state: ApplicationState,
        settings_store: SettingsStore,
        shared_model_runtime: SharedModelRuntime,
        parent: Optional[QObject] = None,
    ) -> None:
        """初始化设置页 ViewModel。"""
        super().__init__(parent)
        self._application_state = application_state
        self._settings_store = settings_store
        self._shared_model_runtime = shared_model_runtime
        self._application_state.state_changed.connect(self.state_changed.emit)
        self._shared_model_runtime.state_changed.connect(self.state_changed.emit)
        self._settings_store.settings_changed.connect(self._on_settings_changed)
        self._settings_store.options_changed.connect(self._on_options_changed)

    @Property("QVariantMap", notify=state_changed)
    def state(self) -> Dict[str, Any]:
        """返回设置页顶部摘要状态。"""
        hardware_summary = dict(self._application_state.state["hardwareSummary"])
        shared_state = self._shared_model_runtime.state
        return {
            "modelReady": shared_state["modelReady"],
            "modelName": shared_state["modelName"],
            "modelStatusText": shared_state["modelStatusText"],
            "modelDetails": shared_state["modelDetails"],
            "taskStatusText": shared_state["taskStatusText"],
            "lastError": shared_state["lastError"],
            "isBusy": shared_state["isBusy"],
            "isLoadingModel": shared_state["isLoadingModel"],
            "loadingProgress": shared_state["loadingProgress"],
            "canLoadModel": shared_state["canLoadModel"],
            "canUnloadModel": shared_state["canUnloadModel"],
            "canReloadModel": shared_state["canReloadModel"],
            "canCancelTask": shared_state["canCancelTask"],
            "hardwareSummary": hardware_summary,
        }

    @Property("QVariantMap", notify=settings_changed)
    def settings(self) -> Dict[str, Any]:
        """返回当前设置。"""
        return self._settings_store.settings

    @Property("QVariantList", notify=options_changed)
    def model_size_options(self) -> List[Dict[str, str]]:
        """返回模型大小选项。"""
        return self._settings_store.model_size_options

    @Property("QVariantList", notify=options_changed)
    def quantization_options(self) -> List[Dict[str, str]]:
        """返回量化模式选项。"""
        return self._settings_store.quantization_options

    @Property("QVariantList", notify=options_changed)
    def device_options(self) -> List[Dict[str, str]]:
        """返回设备选项。"""
        return self._settings_store.device_options

    @Property("QVariantList", notify=options_changed)
    def breakline_method_options(self) -> List[Dict[str, str]]:
        """返回字幕分行算法选项。"""
        return self._settings_store.breakline_method_options

    @Slot(str, object, result=bool)
    def update_setting(self, key: str, value: object) -> bool:
        """更新单个设置项。"""
        return self._settings_store.update_setting(key, value)

    @Slot()
    def reset_defaults(self) -> None:
        """恢复默认设置。"""
        self._settings_store.reset_defaults()

    @Slot()
    def load_model(self) -> None:
        """初始化共享模型。"""
        self._shared_model_runtime.load_model()

    @Slot()
    def reload_model(self) -> None:
        """重载共享模型。"""
        self._shared_model_runtime.reload_model()

    @Slot()
    def unload_model(self) -> None:
        """卸载共享模型。"""
        self._shared_model_runtime.unload_model()

    @Slot(result=bool)
    def cancel_current_task(self) -> bool:
        """取消当前共享模型任务。"""
        return self._shared_model_runtime.cancel_current_task()

    def _on_settings_changed(self) -> None:
        """在设置变化时转发通知。"""
        self.settings_changed.emit()
        self.state_changed.emit()

    def _on_options_changed(self) -> None:
        """在选项变化时转发通知。"""
        self.options_changed.emit()
        self.state_changed.emit()
