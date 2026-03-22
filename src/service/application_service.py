"""应用级共享状态服务。"""

from __future__ import annotations

from importlib import metadata
from typing import Any, Dict, Optional

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication
from qthreadwithreturn import QThreadWithReturn


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
        self._hardware_thread: Optional[QThreadWithReturn] = None
        self._state: Dict[str, Any] = {
            "appName": "QwenASR",
            "version": self._detect_version(),
            "isBusy": False,
            "currentOperation": "",
            "hardwareSummary": {
                "cpuCores": "--",
                "cpuMaxMhz": "--",
                "hasGpu": False,
                "gpuName": "检测中...",
                "gpuMemoryGb": 0.0,
                "systemMemoryGb": 0.0,
            },
        }
        QTimer.singleShot(0, self.refresh_hardware_summary)

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

    @Slot()
    def shutdown(self) -> None:
        """关闭后台探测线程。"""
        if self._hardware_thread is not None and self._hardware_thread.running():
            self._hardware_thread.cancel(force_stop=True)

    @Slot()
    def refresh_hardware_summary(self) -> None:
        """后台刷新硬件摘要，避免阻塞首屏显示。"""
        if self._hardware_thread is not None and self._hardware_thread.running():
            return

        thread = QThreadWithReturn(self._detect_hardware_summary_worker, thread_name="hardware_probe")
        thread.setParent(self)
        self._hardware_thread = thread
        thread.add_done_callback(self._on_hardware_summary_ready)
        thread.add_failure_callback(self._on_hardware_summary_failed)
        thread.finished_signal.connect(self._on_hardware_summary_finished)
        thread.start()

    def _detect_version(self) -> str:
        """检测应用版本。"""
        try:
            return metadata.version("qwenasrgui")
        except metadata.PackageNotFoundError:
            return "0.1.0-dev"

    def _detect_hardware_summary_worker(self) -> Dict[str, Any]:
        """在后台线程中探测硬件信息。"""
        from src.utils.hardware import Hardware

        summary = Hardware().summary()
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

    def _on_hardware_summary_ready(self, summary: Dict[str, Any]) -> None:
        """接收后台硬件探测结果。"""
        self._state["hardwareSummary"] = summary
        self.state_changed.emit()

    def _on_hardware_summary_failed(self, _error: object) -> None:
        """硬件探测失败时保持默认值。"""
        self._state["hardwareSummary"] = {
            "cpuCores": "--",
            "cpuMaxMhz": "--",
            "hasGpu": False,
            "gpuName": "检测失败",
            "gpuMemoryGb": 0.0,
            "systemMemoryGb": 0.0,
        }
        self.state_changed.emit()

    def _on_hardware_summary_finished(self) -> None:
        """清理后台探测线程。"""
        thread = self._hardware_thread
        self._hardware_thread = None
        if thread is not None:
            thread.deleteLater()
