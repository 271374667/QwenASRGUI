"""
系统资源处理器模块。

提供统一的系统硬件检测和资源限制管理接口。
"""

from dataclasses import dataclass, field
from typing import Optional

from src.utils.hardware import Hardware, HardwareSummary
from src.utils.memory_limit import MemoryLimit, MemoryLimitConfig, MemoryLimitError


@dataclass
class ResourceLimitValue:
    """
    资源限制值，支持百分比或精确数值。

    Attributes:
        value: 限制值。如果 is_percentage 为 True，则表示百分比 (0-100)；
               否则表示精确的字节数。
        is_percentage: 是否为百分比模式。
    """

    value: Optional[float] = None
    is_percentage: bool = False

    @classmethod
    def from_percentage(cls, percentage: float) -> "ResourceLimitValue":
        """
        从百分比创建限制值。

        Args:
            percentage: 百分比值，范围 0-100。

        Returns:
            ResourceLimitValue 实例。

        Raises:
            ValueError: 如果百分比值不在 0-100 范围内。
        """
        if not 0 <= percentage <= 100:
            raise ValueError(f"百分比值必须在 0-100 范围内，当前值: {percentage}")
        return cls(value=percentage, is_percentage=True)

    @classmethod
    def from_bytes(cls, bytes_value: int) -> "ResourceLimitValue":
        """
        从字节数创建限制值。

        Args:
            bytes_value: 字节数。

        Returns:
            ResourceLimitValue 实例。
        """
        return cls(value=float(bytes_value), is_percentage=False)

    @classmethod
    def from_gb(cls, gb_value: float) -> "ResourceLimitValue":
        """
        从 GB 单位创建限制值。

        Args:
            gb_value: GB 数值。

        Returns:
            ResourceLimitValue 实例。
        """
        return cls(value=gb_value * (1024**3), is_percentage=False)

    @classmethod
    def disabled(cls) -> "ResourceLimitValue":
        """创建一个禁用的限制值。"""
        return cls(value=None, is_percentage=False)

    @property
    def is_enabled(self) -> bool:
        """是否启用该限制。"""
        return self.value is not None

    def resolve(self, total_bytes: int) -> Optional[int]:
        """
        根据总量解析出实际的字节限制值。

        Args:
            total_bytes: 总可用字节数。

        Returns:
            解析后的限制字节数，如果禁用则返回 None。
        """
        if self.value is None:
            return None
        if self.is_percentage:
            return int(total_bytes * self.value / 100)
        return int(self.value)


@dataclass
class SystemHandlerConfig:
    """
    SystemHandler 配置类。

    用于配置系统资源限制策略，支持百分比和精确数值两种配置方式。

    Attributes:
        enable_memory_limit: 是否启用资源限制功能。
        system_memory_limit: 系统内存限制配置。
        gpu_memory_limit: GPU 显存限制配置。

    Examples:
        # 禁用所有限制
        config = SystemHandlerConfig(enable_memory_limit=False)

        # 使用百分比限制
        config = SystemHandlerConfig(
            enable_memory_limit=True,
            system_memory_limit=ResourceLimitValue.from_percentage(80),
            gpu_memory_limit=ResourceLimitValue.from_percentage(90),
        )

        # 使用精确数值限制 (GB)
        config = SystemHandlerConfig(
            enable_memory_limit=True,
            system_memory_limit=ResourceLimitValue.from_gb(16),
            gpu_memory_limit=ResourceLimitValue.from_gb(8),
        )

        # 混合模式
        config = SystemHandlerConfig(
            enable_memory_limit=True,
            system_memory_limit=ResourceLimitValue.from_percentage(75),
            gpu_memory_limit=ResourceLimitValue.from_gb(6),
        )
    """

    enable_memory_limit: bool = False
    system_memory_limit: ResourceLimitValue = field(
        default_factory=ResourceLimitValue.disabled
    )
    gpu_memory_limit: ResourceLimitValue = field(
        default_factory=ResourceLimitValue.disabled
    )

    @classmethod
    def with_percentage_limits(
        cls,
        system_memory_percent: Optional[float] = None,
        gpu_memory_percent: Optional[float] = None,
    ) -> "SystemHandlerConfig":
        """
        使用百分比创建配置的便捷方法。

        Args:
            system_memory_percent: 系统内存限制百分比 (0-100)，None 表示不限制。
            gpu_memory_percent: GPU 显存限制百分比 (0-100)，None 表示不限制。

        Returns:
            SystemHandlerConfig 实例。
        """
        return cls(
            enable_memory_limit=True,
            system_memory_limit=(
                ResourceLimitValue.from_percentage(system_memory_percent)
                if system_memory_percent is not None
                else ResourceLimitValue.disabled()
            ),
            gpu_memory_limit=(
                ResourceLimitValue.from_percentage(gpu_memory_percent)
                if gpu_memory_percent is not None
                else ResourceLimitValue.disabled()
            ),
        )

    @classmethod
    def with_gb_limits(
        cls,
        system_memory_gb: Optional[float] = None,
        gpu_memory_gb: Optional[float] = None,
    ) -> "SystemHandlerConfig":
        """
        使用 GB 单位创建配置的便捷方法。

        Args:
            system_memory_gb: 系统内存限制 (GB)，None 表示不限制。
            gpu_memory_gb: GPU 显存限制 (GB)，None 表示不限制。

        Returns:
            SystemHandlerConfig 实例。
        """
        return cls(
            enable_memory_limit=True,
            system_memory_limit=(
                ResourceLimitValue.from_gb(system_memory_gb)
                if system_memory_gb is not None
                else ResourceLimitValue.disabled()
            ),
            gpu_memory_limit=(
                ResourceLimitValue.from_gb(gpu_memory_gb)
                if gpu_memory_gb is not None
                else ResourceLimitValue.disabled()
            ),
        )


class SystemHandler:
    """
    系统资源处理器。

    整合硬件检测和资源限制管理功能，提供统一的系统资源管理接口。

    该类负责：
    1. 检测系统硬件信息（CPU、内存、GPU）
    2. 根据配置应用资源限制（系统内存、GPU 显存）
    3. 提供硬件信息查询接口

    Attributes:
        config: 系统处理器配置。
        hardware: 硬件检测器实例。

    Examples:
        # 基本使用
        handler = SystemHandler()
        print(handler.hardware_summary)

        # 启用资源限制
        config = SystemHandlerConfig.with_percentage_limits(
            system_memory_percent=80,
            gpu_memory_percent=90,
        )
        handler = SystemHandler(config)
        handler.apply_limits()

        # 链式调用
        handler = SystemHandler(config).apply_limits()
    """

    def __init__(self, config: Optional[SystemHandlerConfig] = None) -> None:
        """
        初始化系统处理器。

        Args:
            config: 系统处理器配置。如果为 None，则使用默认配置（禁用资源限制）。
        """
        self._config = config or SystemHandlerConfig()
        self._hardware = Hardware()
        self._memory_limiter: Optional[MemoryLimit] = None
        self._limits_applied = False

    # ==================== 公开属性 ====================

    @property
    def config(self) -> SystemHandlerConfig:
        """获取当前配置。"""
        return self._config

    @property
    def hardware(self) -> Hardware:
        """获取硬件检测器实例。"""
        return self._hardware

    @property
    def hardware_summary(self) -> HardwareSummary:
        """获取硬件信息摘要。"""
        return self._hardware.summary()

    @property
    def is_limits_applied(self) -> bool:
        """资源限制是否已应用。"""
        return self._limits_applied

    @property
    def has_gpu(self) -> bool:
        """是否检测到 GPU。"""
        return self._hardware.has_gpu

    @property
    def system_memory_bytes(self) -> int:
        """系统总内存（字节）。"""
        return self._hardware.system_memory_bytes

    @property
    def system_memory_gb(self) -> float:
        """系统总内存（GB）。"""
        return self._hardware.system_memory_gb

    @property
    def gpu_memory_bytes(self) -> Optional[int]:
        """GPU 总显存（字节），如果没有 GPU 则返回 None。"""
        gpu = self._hardware.gpu_info
        return gpu.total_memory_bytes if gpu else None

    @property
    def gpu_memory_gb(self) -> Optional[float]:
        """GPU 总显存（GB），如果没有 GPU 则返回 None。"""
        gpu = self._hardware.gpu_info
        return gpu.total_memory_gb if gpu else None

    # ==================== 公开方法 ====================

    def apply_limits(self) -> "SystemHandler":
        """
        应用资源限制。

        根据配置应用系统内存和 GPU 显存限制。如果配置中禁用了资源限制，
        则此方法不执行任何操作。

        Returns:
            self，支持链式调用。

        Raises:
            MemoryLimitError: 如果应用限制失败。
        """
        if self._limits_applied:
            return self

        if not self._config.enable_memory_limit:
            self._limits_applied = True
            return self

        # 解析配置并创建 MemoryLimitConfig
        memory_config = self._resolve_memory_config()

        # 如果没有任何限制需要应用
        if (
            memory_config.system_memory_limit_bytes is None
            and memory_config.gpu_memory_limit_bytes is None
        ):
            self._limits_applied = True
            return self

        # 创建并应用内存限制器
        self._memory_limiter = MemoryLimit(self.hardware_summary, memory_config)
        self._memory_limiter.apply()
        self._limits_applied = True

        return self

    def get_effective_limits(self) -> dict:
        """
        获取当前生效的资源限制信息。

        Returns:
            包含以下键的字典：
            - enabled: 是否启用资源限制
            - applied: 是否已应用限制
            - system_memory_limit_bytes: 系统内存限制（字节）
            - system_memory_limit_gb: 系统内存限制（GB）
            - gpu_memory_limit_bytes: GPU 显存限制（字节）
            - gpu_memory_limit_gb: GPU 显存限制（GB）
        """
        result: dict = {
            "enabled": self._config.enable_memory_limit,
            "applied": self._limits_applied,
            "system_memory_limit_bytes": None,
            "system_memory_limit_gb": None,
            "gpu_memory_limit_bytes": None,
            "gpu_memory_limit_gb": None,
        }

        if self._memory_limiter:
            limiter_info = self._memory_limiter.get_effective_limits()
            result.update(
                {
                    "system_memory_limit_bytes": limiter_info.get(
                        "system_memory_limit_bytes"
                    ),
                    "system_memory_limit_gb": limiter_info.get(
                        "system_memory_limit_gb"
                    ),
                    "gpu_memory_limit_bytes": limiter_info.get("gpu_memory_limit_bytes"),
                    "gpu_memory_limit_gb": limiter_info.get("gpu_memory_limit_gb"),
                }
            )
        elif self._config.enable_memory_limit:
            # 尚未应用，但可以预览将要应用的限制
            try:
                memory_config = self._resolve_memory_config()
                result.update(
                    {
                        "system_memory_limit_bytes": memory_config.system_memory_limit_bytes,
                        "system_memory_limit_gb": memory_config.system_memory_limit_gb,
                        "gpu_memory_limit_bytes": memory_config.gpu_memory_limit_bytes,
                        "gpu_memory_limit_gb": memory_config.gpu_memory_limit_gb,
                    }
                )
            except Exception:
                pass

        return result

    def print_info(self) -> None:
        """打印系统信息和资源限制状态。"""
        summary = self.hardware_summary

        print("=" * 50)
        print("系统信息")
        print("=" * 50)
        print(f"  CPU 核心数: {summary.cpu_cores}")
        if summary.cpu_max_mhz:
            print(f"  CPU 最大频率: {summary.cpu_max_mhz} MHz")
        print(f"  系统内存: {summary.system_memory_bytes / (1024**3):.2f} GB")

        if summary.has_gpu:
            print(f"  GPU: {summary.gpu_name}")
            if summary.gpu_total_memory_bytes:
                print(
                    f"  GPU 显存: {summary.gpu_total_memory_bytes / (1024**3):.2f} GB"
                )

        print()
        print("=" * 50)
        print("资源限制")
        print("=" * 50)

        limits = self.get_effective_limits()
        print(f"  启用: {limits['enabled']}")
        print(f"  已应用: {limits['applied']}")

        if limits["system_memory_limit_gb"] is not None:
            print(f"  系统内存限制: {limits['system_memory_limit_gb']:.2f} GB")
        else:
            print("  系统内存限制: 无")

        if limits["gpu_memory_limit_gb"] is not None:
            print(f"  GPU 显存限制: {limits['gpu_memory_limit_gb']:.2f} GB")
        else:
            print("  GPU 显存限制: 无")

        print("=" * 50)

    # ==================== 私有方法 ====================

    def _resolve_memory_config(self) -> MemoryLimitConfig:
        """
        解析配置并创建 MemoryLimitConfig。

        Returns:
            MemoryLimitConfig 实例。
        """
        summary = self.hardware_summary

        # 解析系统内存限制
        system_memory_limit = self._config.system_memory_limit.resolve(
            summary.system_memory_bytes
        )

        # 解析 GPU 显存限制
        gpu_memory_limit = None
        if summary.has_gpu and summary.gpu_total_memory_bytes:
            gpu_memory_limit = self._config.gpu_memory_limit.resolve(
                summary.gpu_total_memory_bytes
            )

        return MemoryLimitConfig(
            system_memory_limit_bytes=system_memory_limit,
            gpu_memory_limit_bytes=gpu_memory_limit,
        )


if __name__ == "__main__":
    # 示例 1: 默认配置（禁用限制）
    print("示例 1: 默认配置")
    handler1 = SystemHandler()
    handler1.print_info()
    print()

    # 示例 2: 使用百分比限制
    print("示例 2: 使用百分比限制 (80% 系统内存, 90% GPU 显存)")
    config2 = SystemHandlerConfig.with_percentage_limits(
        system_memory_percent=80,
        gpu_memory_percent=90,
    )
    handler2 = SystemHandler(config2)
    handler2.print_info()
    print()

    # 示例 3: 使用精确数值限制
    print("示例 3: 使用精确数值限制 (8GB 系统内存)")
    config3 = SystemHandlerConfig.with_gb_limits(
        system_memory_gb=8.0,
    )
    handler3 = SystemHandler(config3)
    handler3.print_info()
    print()

    # 示例 4: 应用限制
    print("示例 4: 应用资源限制")
    config4 = SystemHandlerConfig.with_percentage_limits(
        system_memory_percent=90,
    )
    handler4 = SystemHandler(config4)
    try:
        handler4.apply_limits()
        handler4.print_info()
    except MemoryLimitError as e:
        print(f"  应用限制失败: {e}")
