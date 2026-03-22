"""应用级共享状态服务。"""

from __future__ import annotations

from importlib import metadata
from typing import Any, Dict, Optional

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QGuiApplication

from src.utils.hardware import Hardware


class ApplicationService(QObject):
    """应用级共享状态与互斥操作服务。

    该服务负责维护 GUI 的全局共享状态，例如当前是否有后台任务在运行、
    当前执行中的操作名称、应用版本信息以及本机硬件摘要。页面服务通过它
    进行“单任务占用”控制，避免模型加载、转录与对齐任务同时运行。

    Attributes:
        state_changed: 全局状态变化通知。

    Example:
        基本用法::

            app_service = ApplicationService()
            if app_service.begin_operation("加载模型"):
                ...
                app_service.finish_operation()

    Note:
        该服务本身不执行耗时任务，只负责协调与共享元数据。
    """

    state_changed = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        """初始化应用服务。"""
        super().__init__(parent)
        self._hardware = Hardware()
        self._state: Dict[str, Any] = {
            "appName": "QwenASR",
            "version": self._detect_version(),
            "isBusy": False,
            "currentOperation": "",
            "hardwareSummary": self._build_hardware_summary(),
        }

    @Property("QVariantMap", notify=state_changed)
    def state(self) -> Dict[str, Any]:
        """返回供 QML 绑定的应用状态字典。"""
        return dict(self._state)

    def begin_operation(self, operation_name: str) -> bool:
        """尝试开始一个全局独占操作。"""
        if self._state["isBusy"]:
            return False

        self._state["isBusy"] = True
        self._state["currentOperation"] = operation_name
        self.state_changed.emit()
        return True

    def finish_operation(self) -> None:
        """结束当前全局操作。"""
        if not self._state["isBusy"] and not self._state["currentOperation"]:
            return

        self._state["isBusy"] = False
        self._state["currentOperation"] = ""
        self.state_changed.emit()

    @Slot(str, result=bool)
    def copy_text(self, text: str) -> bool:
        """复制文本到系统剪贴板。"""
        if not text:
            return False

        clipboard = QGuiApplication.clipboard()
        clipboard.setText(text)
        return True

    @Slot()
    def request_quit(self) -> None:
        """请求退出应用。"""
        app = QGuiApplication.instance()
        if app is not None:
            app.quit()

    def _detect_version(self) -> str:
        """检测应用版本。"""
        try:
            return metadata.version("qwenasrgui")
        except metadata.PackageNotFoundError:
            return "0.1.0-dev"

    def _build_hardware_summary(self) -> Dict[str, Any]:
        """构建硬件摘要字典。"""
        summary = self._hardware.summary()
        return {
            "cpuCores": summary.cpu_cores,
            "cpuMaxMhz": summary.cpu_max_mhz,
            "hasGpu": summary.has_gpu,
            "gpuName": summary.gpu_name or "未检测到 GPU",
            "gpuMemoryGb": (
                round(summary.gpu_total_memory_bytes / (1024**3), 2)
                if summary.gpu_total_memory_bytes
                else 0.0
            ),
            "systemMemoryGb": round(summary.system_memory_bytes / (1024**3), 2),
        }
