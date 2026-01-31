import platform
from dataclasses import dataclass
from typing import Optional

from src.utils.hardware import HardwareSummary


@dataclass
class MemoryLimitConfig:
    """资源限制配置，所有值都是精确的字节数。"""

    # 系统内存限制（字节），None 表示不限制
    system_memory_limit_bytes: Optional[int] = None
    # GPU 显存限制（字节），None 表示不限制
    gpu_memory_limit_bytes: Optional[int] = None

    @classmethod
    def from_gb(
        cls,
        system_memory_limit_gb: Optional[float] = None,
        gpu_memory_limit_gb: Optional[float] = None,
    ) -> "MemoryLimitConfig":
        """从 GB 单位创建配置的便捷方法。"""
        return cls(
            system_memory_limit_bytes=(
                int(system_memory_limit_gb * (1024**3))
                if system_memory_limit_gb is not None
                else None
            ),
            gpu_memory_limit_bytes=(
                int(gpu_memory_limit_gb * (1024**3))
                if gpu_memory_limit_gb is not None
                else None
            ),
        )

    @property
    def system_memory_limit_gb(self) -> Optional[float]:
        if self.system_memory_limit_bytes is None:
            return None
        return self.system_memory_limit_bytes / (1024**3)

    @property
    def gpu_memory_limit_gb(self) -> Optional[float]:
        if self.gpu_memory_limit_bytes is None:
            return None
        return self.gpu_memory_limit_bytes / (1024**3)


class MemoryLimitError(Exception):
    """资源限制错误。"""

    pass


class MemoryLimit:
    """
    资源限制器，用于限制程序可使用的系统内存和 GPU 显存。

    注意：
    - 系统内存限制仅在 Unix/Linux 系统上有效（使用 resource 模块）
    - GPU 显存限制需要 PyTorch 支持，通过 CUDA 内存分配器实现
    """

    def __init__(
        self, hardware_summary: HardwareSummary, config: MemoryLimitConfig
    ) -> None:
        self._hardware = hardware_summary
        self._config = config
        self._applied = False
        self._validate_config()

    def _validate_config(self) -> None:
        """验证配置是否合理。"""
        # 验证系统内存限制
        if self._config.system_memory_limit_bytes is not None:
            if self._config.system_memory_limit_bytes <= 0:
                raise MemoryLimitError("系统内存限制必须大于 0")
            if (
                self._config.system_memory_limit_bytes
                > self._hardware.system_memory_bytes
            ):
                raise MemoryLimitError(
                    f"系统内存限制 ({self._config.system_memory_limit_gb:.2f} GB) "
                    f"超过可用系统内存 ({self._hardware.system_memory_bytes / (1024**3):.2f} GB)"
                )

        # 验证 GPU 显存限制
        if self._config.gpu_memory_limit_bytes is not None:
            if not self._hardware.has_gpu:
                raise MemoryLimitError("无法设置 GPU 显存限制：未检测到 GPU")
            if self._config.gpu_memory_limit_bytes <= 0:
                raise MemoryLimitError("GPU 显存限制必须大于 0")
            if self._hardware.gpu_total_memory_bytes is not None:
                if (
                    self._config.gpu_memory_limit_bytes
                    > self._hardware.gpu_total_memory_bytes
                ):
                    raise MemoryLimitError(
                        f"GPU 显存限制 ({self._config.gpu_memory_limit_gb:.2f} GB) "
                        f"超过可用 GPU 显存 ({self._hardware.gpu_total_memory_bytes / (1024**3):.2f} GB)"
                    )

    @property
    def config(self) -> MemoryLimitConfig:
        return self._config

    @property
    def hardware(self) -> HardwareSummary:
        return self._hardware

    @property
    def is_applied(self) -> bool:
        return self._applied

    def apply(self) -> "MemoryLimit":
        """
        应用资源限制。

        返回 self 以支持链式调用。
        """
        if self._applied:
            return self

        self._apply_system_memory_limit()
        self._apply_gpu_memory_limit()
        self._applied = True
        return self

    def _apply_system_memory_limit(self) -> None:
        """应用系统内存限制。"""
        if self._config.system_memory_limit_bytes is None:
            return

        system = platform.system()

        if system in ("Linux", "Darwin"):
            # Unix/Linux/macOS: 使用 resource 模块
            try:
                import resource  # type: ignore[import-not-found]

                # 设置虚拟内存限制 (RLIMIT_AS)
                soft, hard = resource.getrlimit(resource.RLIMIT_AS)  # type: ignore[attr-defined]
                new_limit = self._config.system_memory_limit_bytes
                # 不能超过硬限制
                if hard != resource.RLIM_INFINITY and new_limit > hard:  # type: ignore[attr-defined]
                    new_limit = hard
                resource.setrlimit(resource.RLIMIT_AS, (new_limit, hard))  # type: ignore[attr-defined]
            except (ImportError, OSError, ValueError) as e:
                raise MemoryLimitError(f"无法设置系统内存限制: {e}") from e

        elif system == "Windows":
            # Windows: 使用 Job Objects
            self._apply_windows_memory_limit()

        else:
            raise MemoryLimitError(f"不支持的操作系统: {system}")

    def _apply_windows_memory_limit(self) -> None:
        """在 Windows 上应用内存限制。"""
        if self._config.system_memory_limit_bytes is None:
            return

        try:
            import ctypes
            from ctypes import wintypes

            # Windows API 常量
            JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
            JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
            JobObjectExtendedLimitInformation = 9

            # 定义 JOBOBJECT_BASIC_LIMIT_INFORMATION 结构
            class IO_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("ReadOperationCount", ctypes.c_ulonglong),
                    ("WriteOperationCount", ctypes.c_ulonglong),
                    ("OtherOperationCount", ctypes.c_ulonglong),
                    ("ReadTransferCount", ctypes.c_ulonglong),
                    ("WriteTransferCount", ctypes.c_ulonglong),
                    ("OtherTransferCount", ctypes.c_ulonglong),
                ]

            class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("PerProcessUserTimeLimit", ctypes.c_int64),
                    ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.POINTER(ctypes.c_ulong)),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD),
                ]

            class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                    ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t),
                ]

            kernel32 = ctypes.windll.kernel32

            # Windows API 常量 - 进程访问权限
            PROCESS_SET_QUOTA = 0x0100
            PROCESS_TERMINATE = 0x0001

            # 创建 Job Object
            job_handle = kernel32.CreateJobObjectW(None, None)
            if not job_handle:
                raise MemoryLimitError("无法创建 Job Object")

            # 设置内存限制
            limit_info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            limit_info.BasicLimitInformation.LimitFlags = (
                JOB_OBJECT_LIMIT_PROCESS_MEMORY | JOB_OBJECT_LIMIT_JOB_MEMORY
            )
            limit_info.ProcessMemoryLimit = self._config.system_memory_limit_bytes
            limit_info.JobMemoryLimit = self._config.system_memory_limit_bytes

            success = kernel32.SetInformationJobObject(
                job_handle,
                JobObjectExtendedLimitInformation,
                ctypes.byref(limit_info),
                ctypes.sizeof(limit_info),
            )
            if not success:
                kernel32.CloseHandle(job_handle)
                raise MemoryLimitError("无法设置 Job Object 内存限制")

            # 获取当前进程 ID 并打开进程句柄
            import os

            current_pid = os.getpid()
            process_handle = kernel32.OpenProcess(
                PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, current_pid
            )
            if not process_handle:
                error_code = kernel32.GetLastError()
                kernel32.CloseHandle(job_handle)
                raise MemoryLimitError(f"无法打开当前进程句柄，错误码: {error_code}")

            # 将当前进程添加到 Job Object
            success = kernel32.AssignProcessToJobObject(job_handle, process_handle)
            kernel32.CloseHandle(process_handle)  # 关闭进程句柄

            if not success:
                error_code = kernel32.GetLastError()
                kernel32.CloseHandle(job_handle)
                # 错误码 5 表示 ACCESS_DENIED，可能进程已经在一个 Job 中
                if error_code == 5:
                    # 在某些情况下（如调试模式），进程可能已经在一个 Job 中
                    # 这种情况下我们跳过，但记录警告
                    import warnings

                    warnings.warn(
                        "无法将进程添加到 Job Object（可能已经在另一个 Job 中），内存限制可能未生效"
                    )
                    return
                raise MemoryLimitError(
                    f"无法将进程添加到 Job Object，错误码: {error_code}"
                )

            # 保存 job_handle 以防止被垃圾回收
            self._job_handle = job_handle

        except ImportError as e:
            raise MemoryLimitError(f"无法导入 ctypes 模块: {e}") from e

    def _apply_gpu_memory_limit(self) -> None:
        """应用 GPU 显存限制。"""
        if self._config.gpu_memory_limit_bytes is None:
            return

        if not self._hardware.has_gpu:
            return

        try:
            import torch

            if not torch.cuda.is_available():
                raise MemoryLimitError("CUDA 不可用")

            # 计算显存限制比例
            if self._hardware.gpu_total_memory_bytes is None:
                raise MemoryLimitError("无法获取 GPU 总显存")

            fraction = (
                self._config.gpu_memory_limit_bytes
                / self._hardware.gpu_total_memory_bytes
            )
            fraction = max(0.0, min(1.0, fraction))  # 确保在 [0, 1] 范围内

            # 设置每个进程的显存使用比例
            # 注意：这必须在任何 CUDA 操作之前调用
            torch.cuda.set_per_process_memory_fraction(fraction)

        except ImportError as e:
            raise MemoryLimitError(f"无法导入 torch 模块: {e}") from e
        except RuntimeError as e:
            raise MemoryLimitError(f"无法设置 GPU 显存限制: {e}") from e

    def get_effective_limits(self) -> dict:
        """获取当前生效的资源限制信息。"""
        result = {
            "system_memory_limit_bytes": self._config.system_memory_limit_bytes,
            "system_memory_limit_gb": self._config.system_memory_limit_gb,
            "gpu_memory_limit_bytes": self._config.gpu_memory_limit_bytes,
            "gpu_memory_limit_gb": self._config.gpu_memory_limit_gb,
            "applied": self._applied,
        }

        # 尝试获取实际的系统内存限制
        if platform.system() in ("Linux", "Darwin"):
            try:
                import resource  # type: ignore[import-not-found]

                soft, hard = resource.getrlimit(resource.RLIMIT_AS)  # type: ignore[attr-defined]
                result["actual_system_memory_limit_bytes"] = (
                    soft if soft != resource.RLIM_INFINITY else None  # type: ignore[attr-defined]
                )
            except Exception:
                pass

        return result


if __name__ == "__main__":
    from src.utils.hardware import Hardware

    hw = Hardware()
    summary = hw.summary()

    print("Hardware Summary:")
    print(f"  System Memory: {summary.system_memory_bytes / (1024**3):.2f} GB")
    if summary.has_gpu:
        print(f"  GPU: {summary.gpu_name}")
        print(
            f"  GPU Memory: {summary.gpu_total_memory_bytes / (1024**3):.2f} GB"
            if summary.gpu_total_memory_bytes
            else "  GPU Memory: Unknown"
        )

    # 示例：限制系统内存为 8GB，GPU 显存为 4GB
    config = MemoryLimitConfig.from_gb(
        system_memory_limit_gb=8.0,
        gpu_memory_limit_gb=4.0 if summary.has_gpu else None,
    )

    print("\nMemory Limit Config:")
    print(f"  System Memory Limit: {config.system_memory_limit_gb:.2f} GB")
    if config.gpu_memory_limit_gb:
        print(f"  GPU Memory Limit: {config.gpu_memory_limit_gb:.2f} GB")

    try:
        limiter = MemoryLimit(summary, config)
        limiter.apply()
        print("\nMemory limits applied successfully!")
        print("Effective Limits:", limiter.get_effective_limits())
    except MemoryLimitError as e:
        print(f"\nFailed to apply memory limits: {e}")
