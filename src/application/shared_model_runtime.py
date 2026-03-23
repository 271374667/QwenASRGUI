"""共享模型运行时。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from loguru import logger
from PySide6.QtCore import QObject, Property, Signal, Slot
from qthreadwithreturn import QThreadWithReturn

from src.application.app_state import ApplicationState
from src.application.settings_store import SettingsStore

if TYPE_CHECKING:
    from src.model import ASRService


class SharedModelRuntime(QObject):
    """管理全局共享 ASR 模型的生命周期与状态。"""

    state_changed = Signal()

    def __init__(
        self,
        application_state: ApplicationState,
        settings_store: SettingsStore,
        parent: Optional[QObject] = None,
    ) -> None:
        """初始化共享模型运行时。"""
        super().__init__(parent)
        self._application_state = application_state
        self._settings_store = settings_store
        self._asr_service: Optional["ASRService"] = None
        self._asr_signals_connected = False
        self._task_thread: Optional[QThreadWithReturn] = None
        self._cancel_requested = False
        self._state: Dict[str, Any] = {
            "modelReady": False,
            "modelStatusText": "未加载",
            "modelName": "Qwen3-ASR",
            "modelDetails": "共享模型尚未加载",
            "loadingProgress": 0,
            "isBusy": False,
            "isLoadingModel": False,
            "taskStatusText": "共享模型尚未加载",
            "lastError": "",
            "canLoadModel": True,
            "canUnloadModel": False,
            "canReloadModel": False,
            "canCancelTask": False,
        }
        self._application_state.state_changed.connect(self._on_application_state_changed)
        self._refresh_state()

    @Property("QVariantMap", notify=state_changed)
    def state(self) -> Dict[str, Any]:
        """返回供 ViewModel 消费的共享模型状态。"""
        return dict(self._state)

    @property
    def asr_service(self):
        """返回底层共享 ASR 服务。"""
        return self._ensure_asr_service()

    @Slot()
    def load_model(self) -> None:
        """加载共享模型。"""
        self._start_background_task(
            "加载共享模型",
            self._load_model_worker,
            self._on_model_loaded,
        )

    @Slot()
    def reload_model(self) -> None:
        """重载共享模型。"""
        self._start_background_task(
            "重新加载共享模型",
            self._reload_model_worker,
            self._on_model_loaded,
        )

    @Slot()
    def unload_model(self) -> None:
        """卸载共享模型。"""
        self._start_background_task(
            "卸载共享模型",
            self._unload_model_worker,
            self._on_model_unloaded,
        )

    @Slot(result=bool)
    def cancel_current_task(self) -> bool:
        """取消当前共享模型任务。"""
        if self._task_thread is None or not self._task_thread.running():
            return False

        self._cancel_requested = True
        self._state["taskStatusText"] = "正在强制停止当前任务..."
        self._state["lastError"] = ""
        self.state_changed.emit()
        return self._task_thread.cancel(force_stop=True)

    @Slot()
    def shutdown(self) -> None:
        """关闭共享模型后台任务。"""
        if self._task_thread is not None and self._task_thread.running():
            self._task_thread.cancel(force_stop=True)

    def _load_model_worker(self) -> Dict[str, Any]:
        """后台执行模型加载。"""
        asr_service = self._ensure_asr_service()
        system_config = self._settings_store.build_system_config()
        if system_config.enable_memory_limit:
            from src.model import SystemHandler

            SystemHandler(system_config).apply_limits()

        success = asr_service.load_model(self._settings_store.build_model_config())
        if not success:
            raise RuntimeError("模型加载失败")

        asr_service.configure_interface(self._settings_store.build_asr_config())
        return {"success": True}

    def _reload_model_worker(self) -> Dict[str, Any]:
        """后台执行模型重载。"""
        asr_service = self._ensure_asr_service()
        system_config = self._settings_store.build_system_config()
        if system_config.enable_memory_limit:
            from src.model import SystemHandler

            SystemHandler(system_config).apply_limits()

        success = asr_service.reload_model(self._settings_store.build_model_config())
        if not success:
            raise RuntimeError("模型重新加载失败")

        asr_service.configure_interface(self._settings_store.build_asr_config())
        return {"success": True}

    def _unload_model_worker(self) -> Dict[str, Any]:
        """后台执行模型卸载。"""
        self._ensure_asr_service().unload_model()
        return {"success": True}

    def _start_background_task(
        self,
        operation_name: str,
        worker: Any,
        result_handler: Any,
    ) -> None:
        """统一启动共享模型后台任务。"""
        if not self._application_state.begin_operation(operation_name):
            self._set_error("已有后台任务正在运行，请稍后再试")
            return

        self._state["isBusy"] = True
        self._state["isLoadingModel"] = operation_name != "卸载共享模型"
        self._state["taskStatusText"] = f"正在{operation_name}..."
        self._state["lastError"] = ""
        self._cancel_requested = False
        self._refresh_state()

        thread = QThreadWithReturn(worker, thread_name=operation_name)
        thread.setParent(self)
        self._task_thread = thread
        thread.add_done_callback(result_handler)
        thread.add_failure_callback(self._on_task_error)
        thread.finished_signal.connect(self._on_task_finished)
        thread.start()

    def _build_idle_task_status(self, model_ready: bool) -> str:
        """根据当前模型状态生成空闲时提示文案。"""
        if self._state["lastError"]:
            return str(self._state["lastError"])
        if model_ready:
            return "共享模型已就绪"
        return "共享模型尚未加载"

    def _refresh_state(self) -> None:
        """刷新共享模型状态。"""
        if self._asr_service is None:
            model_ready = False
            model_status_text = "未加载"
            model_name = "Qwen3-ASR"
            quantization = "auto"
        else:
            model_ready = self._asr_service.is_ready
            model_status_text = self._asr_service.status.value
            model_name = self._asr_service.model_name
            quantization = (
                self._asr_service.actual_quantization_mode.value
                if self._asr_service.actual_quantization_mode is not None
                else "auto"
            )
        app_busy = bool(self._application_state.state["isBusy"])
        task_status_text = (
            str(self._state["taskStatusText"])
            if self._state["isBusy"]
            else self._build_idle_task_status(model_ready)
        )
        self._state.update(
            {
                "modelReady": model_ready,
                "modelStatusText": model_status_text,
                "modelName": model_name,
                "modelDetails": (
                    f"量化模式: {quantization}" if model_ready else "共享模型尚未加载"
                ),
                "taskStatusText": task_status_text,
                "canLoadModel": (not model_ready) and (not app_busy),
                "canUnloadModel": model_ready and (not app_busy),
                "canReloadModel": model_ready and (not app_busy),
                "canCancelTask": bool(self._state["isBusy"]),
            }
        )
        self.state_changed.emit()

    def _set_error(self, message: str) -> None:
        """设置错误信息。"""
        self._state["taskStatusText"] = message
        self._state["lastError"] = message
        self._refresh_state()
        logger.error(message)

    def _on_shared_status_changed(self, _status: object) -> None:
        """同步底层 ASR 状态。"""
        self._refresh_state()

    def _on_loading_progress(self, value: int) -> None:
        """同步模型加载进度。"""
        self._state["loadingProgress"] = value
        self.state_changed.emit()

    def _on_application_state_changed(self) -> None:
        """根据全局任务锁刷新按钮可用性。"""
        self._refresh_state()

    def _on_model_loaded(self, _result: object) -> None:
        """处理模型加载完成。"""
        self._state["taskStatusText"] = "共享模型已就绪"
        self._state["lastError"] = ""
        self._refresh_state()

    def _on_model_unloaded(self, _result: object) -> None:
        """处理模型卸载完成。"""
        self._state["loadingProgress"] = 0
        self._state["taskStatusText"] = "共享模型已卸载"
        self._state["lastError"] = ""
        self._refresh_state()

    def _on_task_error(self, error: object) -> None:
        """处理后台任务异常。"""
        message = str(error)
        self._state["taskStatusText"] = message
        self._state["lastError"] = message
        self.state_changed.emit()

    def _on_task_finished(self) -> None:
        """清理后台任务并刷新共享状态。"""
        thread = self._task_thread
        self._task_thread = None
        self._state["isBusy"] = False
        self._state["isLoadingModel"] = False
        if self._cancel_requested:
            self._state["taskStatusText"] = "任务已强制停止"
            self._state["lastError"] = ""
        self._cancel_requested = False
        if self._asr_service is None or not self._asr_service.is_ready:
            self._state["loadingProgress"] = 0
        self._application_state.finish_operation()
        self._refresh_state()
        if thread is not None:
            thread.deleteLater()

    def _ensure_asr_service(self):
        """按需创建共享 ASR 服务，避免启动时导入重模块。"""
        if self._asr_service is None:
            from src.model import ASRService

            self._asr_service = ASRService()

        if not self._asr_signals_connected:
            self._asr_service.signals.status_changed.connect(self._on_shared_status_changed)
            self._asr_service.signals.loading_progress.connect(self._on_loading_progress)
            self._asr_signals_connected = True

        return self._asr_service
