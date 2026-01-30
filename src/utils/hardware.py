import os
import time
from dataclasses import asdict, dataclass
from typing import Optional

import psutil


@dataclass(frozen=True)
class GpuInfo:
    name: str
    total_memory_bytes: int

    @property
    def total_memory_gb(self) -> float:
        return self.total_memory_bytes / (1024**3)


@dataclass(frozen=True)
class HardwareSummary:
    cpu_cores: int
    cpu_max_mhz: Optional[int]
    cpu_ops_per_sec: float
    has_gpu: bool
    gpu_name: Optional[str]
    gpu_total_memory_bytes: Optional[int]
    system_memory_bytes: int


class Hardware:
    """
    Provide basic hardware information needed for runtime config decisions.
    """

    def __init__(self) -> None:
        self._cpu_max_mhz: Optional[int] = None
        self._cpu_ops_per_sec: Optional[float] = None
        self._gpu_info: Optional[GpuInfo] = None
        self._has_gpu: Optional[bool] = None
        self._system_memory_bytes: Optional[int] = None

    @property
    def cpu_cores(self) -> int:
        return os.cpu_count() or 0

    @property
    def cpu_max_mhz(self) -> Optional[int]:
        if self._cpu_max_mhz is None:
            self._cpu_max_mhz = self._detect_cpu_max_mhz()
        return self._cpu_max_mhz

    @property
    def cpu_ops_per_sec(self) -> float:
        if self._cpu_ops_per_sec is None:
            self._cpu_ops_per_sec = self._benchmark_cpu_ops()
        return self._cpu_ops_per_sec

    @property
    def has_gpu(self) -> bool:
        if self._has_gpu is None:
            self._gpu_info = self._detect_gpu_info()
            self._has_gpu = self._gpu_info is not None
        return self._has_gpu

    @property
    def gpu_info(self) -> Optional[GpuInfo]:
        if self._has_gpu is None:
            _ = self.has_gpu
        return self._gpu_info

    @property
    def system_memory_bytes(self) -> int:
        if self._system_memory_bytes is None:
            self._system_memory_bytes = self._detect_system_memory_bytes()
        return self._system_memory_bytes

    @property
    def system_memory_gb(self) -> float:
        return self.system_memory_bytes / (1024**3)

    def summary(self) -> HardwareSummary:
        gpu = self.gpu_info
        return HardwareSummary(
            cpu_cores=self.cpu_cores,
            cpu_max_mhz=self.cpu_max_mhz,
            cpu_ops_per_sec=self.cpu_ops_per_sec,
            has_gpu=self.has_gpu,
            gpu_name=gpu.name if gpu else None,
            gpu_total_memory_bytes=gpu.total_memory_bytes if gpu else None,
            system_memory_bytes=self.system_memory_bytes,
        )

    def _benchmark_cpu_ops(self, duration_sec: float = 0.25) -> float:
        # Simple integer ops benchmark to estimate relative compute speed.
        start = time.perf_counter()
        count = 0
        x = 1
        while time.perf_counter() - start < duration_sec:
            x = (x * 1103515245 + 12345) & 0x7FFFFFFF
            count += 1
        elapsed = time.perf_counter() - start
        if elapsed <= 0:
            return 0.0
        return count / elapsed

    def _detect_cpu_max_mhz(self) -> Optional[int]:
        try:
            freq = psutil.cpu_freq()
            if not freq:
                return None
            return int(freq.max) if freq.max else int(freq.current)
        except Exception:
            return None

    def _detect_gpu_info(self) -> Optional[GpuInfo]:
        try:
            import torch

            if not torch.cuda.is_available():
                return None
            index = torch.cuda.current_device()
            props = torch.cuda.get_device_properties(index)
            return GpuInfo(name=props.name, total_memory_bytes=int(props.total_memory))
        except Exception:
            return None

    def _detect_system_memory_bytes(self) -> int:
        try:
            return int(psutil.virtual_memory().total)
        except Exception:
            return 0

    def get_gpu_available_memory_bytes(self, device_id: int = 0) -> int:
        """
        获取 GPU 可用显存（字节）
        
        Args:
            device_id: GPU 设备 ID
            
        Returns:
            可用显存字节数，如果无 GPU 返回 0
        """
        try:
            import torch

            if not torch.cuda.is_available():
                return 0

            total = torch.cuda.get_device_properties(device_id).total_memory
            reserved = torch.cuda.memory_reserved(device_id)
            available = total - reserved

            return max(0, available)
        except Exception:
            return 0

    def get_gpu_available_memory_gb(self, device_id: int = 0) -> float:
        """
        获取 GPU 可用显存（GB）
        
        Args:
            device_id: GPU 设备 ID
            
        Returns:
            可用显存 GB，如果无 GPU 返回 0
        """
        return self.get_gpu_available_memory_bytes(device_id) / (1024**3)

    def get_gpu_memory_limit_fraction(self, device_id: int = 0) -> float:
        """
        获取 PyTorch 设置的显存限制比例
        
        Args:
            device_id: GPU 设备 ID
            
        Returns:
            显存限制比例 (0.0-1.0)，1.0 表示无限制
        """
        try:
            import torch

            if not torch.cuda.is_available():
                return 1.0

            return torch.cuda.get_per_process_memory_fraction(device_id)
        except Exception:
            return 1.0

    def get_gpu_effective_available_memory_bytes(self, device_id: int = 0) -> int:
        """
        获取考虑显存限制后的实际可用显存（字节）
        
        Args:
            device_id: GPU 设备 ID
            
        Returns:
            实际可用显存字节数
        """
        try:
            import torch

            if not torch.cuda.is_available():
                return 0

            total = torch.cuda.get_device_properties(device_id).total_memory
            allocated = torch.cuda.memory_allocated(device_id)
            reserved = torch.cuda.memory_reserved(device_id)

            # 基础可用显存
            available = total - reserved

            # 检查是否有显存限制
            limit_fraction = self.get_gpu_memory_limit_fraction(device_id)
            if limit_fraction < 1.0:
                # 有限制，计算实际可用
                limited_total = int(total * limit_fraction)
                available = min(available, limited_total - allocated)

            return max(0, available)
        except Exception:
            return 0

    def get_gpu_effective_available_memory_gb(self, device_id: int = 0) -> float:
        """
        获取考虑显存限制后的实际可用显存（GB）
        
        Args:
            device_id: GPU 设备 ID
            
        Returns:
            实际可用显存 GB
        """
        return self.get_gpu_effective_available_memory_bytes(device_id) / (1024**3)

    def get_gpu_memory_status(self, device_id: int = 0) -> dict:
        """
        获取 GPU 显存状态摘要
        
        Args:
            device_id: GPU 设备 ID
            
        Returns:
            包含显存状态的字典
        """
        try:
            import torch

            if not torch.cuda.is_available():
                return {"available": False}

            total = torch.cuda.get_device_properties(device_id).total_memory
            allocated = torch.cuda.memory_allocated(device_id)
            reserved = torch.cuda.memory_reserved(device_id)
            limit_fraction = self.get_gpu_memory_limit_fraction(device_id)

            return {
                "available": True,
                "total_bytes": total,
                "total_gb": total / (1024**3),
                "allocated_bytes": allocated,
                "allocated_gb": allocated / (1024**3),
                "reserved_bytes": reserved,
                "reserved_gb": reserved / (1024**3),
                "free_bytes": total - reserved,
                "free_gb": (total - reserved) / (1024**3),
                "limit_fraction": limit_fraction,
                "effective_available_bytes": self.get_gpu_effective_available_memory_bytes(device_id),
                "effective_available_gb": self.get_gpu_effective_available_memory_gb(device_id),
            }
        except Exception:
            return {"available": False}


if __name__ == "__main__":
    hw = Hardware()
    print("Hardware Summary:")
    # 打印硬件信息摘要
    for key, value in asdict(hw.summary()).items():
        print(f"  {key}: {value}")
