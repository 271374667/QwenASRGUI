"""
ASR Model Holder Module
模型容器单例，管理模型的生命周期

职责:
- 模型加载/卸载
- 状态管理 (NOT_LOADED → LOADING → READY)
- 量化模式自动选择
- 模型大小自动选择
- 显存管理
"""

import torch
import warnings
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

from loguru import logger
from transformers import logging as transformers_logging
from qwen_asr import Qwen3ASRModel

from src.core import paths
from src.utils.hardware import Hardware
from src.utils.singleton import singleton


# 抑制 transformers 警告
transformers_logging.set_verbosity_error()
warnings.filterwarnings("ignore", message=".*pad_token_id.*")


class ModelStatus(Enum):
    """模型状态枚举"""

    NOT_LOADED = "未加载"
    LOADING = "加载中"
    READY = "就绪"
    PROCESSING = "处理中"
    ERROR = "错误"


class QuantizationMode(Enum):
    """量化模式枚举"""

    NONE = "fp16"  # 无量化，使用 fp16
    INT8 = "int8"  # 8-bit 量化
    INT4 = "int4"  # 4-bit 量化
    AUTO = "auto"  # 自动选择


class ModelSize(Enum):
    """模型大小枚举"""

    LARGE = "large"  # Qwen3-ASR-1.7B
    SMALL = "small"  # Qwen3-ASR-0.6B
    AUTO = "auto"  # 自动选择（根据显存）


# 不同量化模式下模型的预估显存需求（GB）
# 基于 Qwen3-ASR-1.7B + Forced Aligner 模型估算
# 注意：KV cache 和激活值在推理时仍使用 fp16，需要额外显存
VRAM_REQUIREMENTS = {
    QuantizationMode.NONE: 6.0,  # fp16: ~3.4GB ASR + ~1.2GB Aligner + 1.4GB 推理开销
    QuantizationMode.INT8: 4.5,  # int8: ~1.7GB ASR + ~1.2GB Aligner + 1.6GB 推理开销(KV cache仍fp16)
    QuantizationMode.INT4: 3.5,  # int4: ~0.85GB ASR + ~1.2GB Aligner + 1.45GB 推理开销
}

# 小模型（Qwen3-ASR-0.6B）的显存需求（GB）
VRAM_REQUIREMENTS_SMALL = {
    QuantizationMode.NONE: 3.5,  # fp16: ~1.2GB ASR + ~1.2GB Aligner + 1.1GB 推理开销
    QuantizationMode.INT8: 2.8,  # int8: ~0.6GB ASR + ~1.2GB Aligner + 1.0GB 推理开销
    QuantizationMode.INT4: 2.2,  # int4: ~0.3GB ASR + ~1.2GB Aligner + 0.7GB 推理开销
}

# 模型名称映射
MODEL_NAMES = {
    ModelSize.LARGE: "Qwen3-ASR-1.7B",
    ModelSize.SMALL: "Qwen3-ASR-0.6B",
}


@dataclass
class ModelConfig:
    """模型加载配置"""

    asr_model_path: str = field(default_factory=lambda: str(paths.ASR_MODEL_DIR))
    aligner_model_path: str = field(
        default_factory=lambda: str(paths.FORCED_ALIGNER_MODEL_DIR)
    )
    dtype: torch.dtype = torch.float16
    device: str = "cuda:0"
    quantization_mode: QuantizationMode = QuantizationMode.AUTO
    model_size: ModelSize = ModelSize.AUTO
    auto_quantization_safety_margin: float = 0.5
    # 模型相关参数
    max_inference_batch_size: int = 32
    max_new_tokens: int = 270  # 约 15 秒 * 18 token/秒

    def __post_init__(self) -> None:
        """根据 model_size 自动设置模型路径（仅当使用默认路径时）"""
        if self.model_size == ModelSize.SMALL:
            if self.asr_model_path == str(paths.ASR_MODEL_DIR):
                self.asr_model_path = str(paths.ASR_SMALL_MODEL_DIR)


@singleton
class ASRModelHolder:
    """
    ASR 模型容器单例

    负责管理 ASR 模型的生命周期，包括加载、卸载和状态管理。
    可独立于 Qt 使用，便于测试和非 GUI 场景。

    使用示例::

        # 获取单例并加载模型
        holder = ASRModelHolder()
        holder.load()

        # 检查状态
        if holder.is_ready:
            model = holder.model
            # 使用模型...

        # 卸载模型
        holder.unload()
    """

    def __init__(self, config: Optional[ModelConfig] = None):
        """
        初始化模型容器

        Args:
            config: 模型配置，默认使用 ModelConfig 默认值
        """
        self._config = config or ModelConfig()
        self._model: Optional[Qwen3ASRModel] = None
        self._status = ModelStatus.NOT_LOADED
        self._hardware = Hardware()
        self._actual_quantization_mode: Optional[QuantizationMode] = None
        self._actual_model_size: Optional[ModelSize] = None
        # 用于存储实际使用的模型路径（可能因自动选择而变化）
        self._effective_asr_model_path: Optional[str] = None

        logger.info("ASRModelHolder 初始化完成")

    @property
    def config(self) -> ModelConfig:
        """获取模型配置"""
        return self._config

    @property
    def status(self) -> ModelStatus:
        """获取当前模型状态"""
        return self._status

    @property
    def is_ready(self) -> bool:
        """检查模型是否就绪"""
        return self._status == ModelStatus.READY

    @property
    def model(self) -> Optional[Qwen3ASRModel]:
        """获取已加载的模型"""
        return self._model

    @property
    def forced_aligner(self):
        """获取强制对齐器"""
        if self._model is not None and hasattr(self._model, "forced_aligner"):
            return self._model.forced_aligner
        return None

    @property
    def actual_quantization_mode(self) -> Optional[QuantizationMode]:
        """获取实际使用的量化模式"""
        return self._actual_quantization_mode

    @property
    def actual_model_size(self) -> Optional[ModelSize]:
        """获取实际使用的模型大小"""
        return self._actual_model_size

    @property
    def model_name(self) -> str:
        """获取当前使用的模型名称"""
        if self._actual_model_size is not None:
            return MODEL_NAMES.get(self._actual_model_size, "Unknown")
        # 根据配置的模型路径判断
        if (
            self._config.model_size == ModelSize.SMALL
            or str(paths.ASR_SMALL_MODEL_DIR) in self._config.asr_model_path
        ):
            return MODEL_NAMES[ModelSize.SMALL]
        return MODEL_NAMES[ModelSize.LARGE]

    def load(self, config: Optional[ModelConfig] = None) -> None:
        """
        加载模型（支持自动量化降级和模型大小自动选择）

        Args:
            config: 可选的新配置，如果提供则替换当前配置
        """
        if config is not None:
            self._config = config

        if self._status == ModelStatus.READY:
            logger.warning("模型已加载，跳过重复加载")
            return

        self._status = ModelStatus.LOADING
        logger.info("开始加载 ASR 模型...")

        # 确定模型大小
        model_size = self._determine_model_size()
        self._actual_model_size = model_size

        # 确定量化模式
        quantization_mode = self._determine_quantization_mode()
        self._actual_quantization_mode = quantization_mode

        # 打印加载参数
        self._log_loading_params(quantization_mode)

        try:
            # 构建模型加载参数
            model_kwargs = self._build_model_kwargs(quantization_mode)
            self._effective_asr_model_path = model_kwargs["pretrained_model_name_or_path"]

            self._model = Qwen3ASRModel.from_pretrained(**model_kwargs)
            self._status = ModelStatus.READY
            logger.success(f"模型加载完成: {self.model_name}")
            self._log_gpu_status()

        except torch.cuda.OutOfMemoryError as e:
            # 首先尝试量化降级
            lower_mode = self._get_lower_quantization_mode(quantization_mode)
            if lower_mode is not None:
                logger.warning(f"显存不足，尝试降级到 {lower_mode.value} 量化模式...")
                self._status = ModelStatus.NOT_LOADED
                torch.cuda.empty_cache()
                self._config.quantization_mode = lower_mode
                self.load()
            # 如果量化已是最低，尝试切换到小模型
            elif self._actual_model_size == ModelSize.LARGE:
                logger.warning("显存不足且已是最低量化精度，尝试切换到小模型...")
                self._status = ModelStatus.NOT_LOADED
                torch.cuda.empty_cache()
                self._config.model_size = ModelSize.SMALL
                self._config.asr_model_path = str(paths.ASR_SMALL_MODEL_DIR)
                self._config.quantization_mode = QuantizationMode.AUTO  # 重置量化模式
                self.load()
            else:
                self._status = ModelStatus.ERROR
                logger.error(f"模型加载失败（显存不足）: {e}")
                raise
        except Exception as e:
            self._status = ModelStatus.ERROR
            logger.error(f"模型加载失败: {e}")
            raise

    def unload(self) -> None:
        """卸载模型释放显存"""
        if self._model is not None:
            del self._model
            self._model = None
            torch.cuda.empty_cache()
            self._status = ModelStatus.NOT_LOADED
            self._actual_quantization_mode = None
            self._actual_model_size = None
            self._effective_asr_model_path = None
            logger.info("模型已卸载，显存已释放")

    def reload(self, config: Optional[ModelConfig] = None) -> None:
        """
        重新加载模型

        Args:
            config: 可选的新配置
        """
        self.unload()
        self.load(config)

    def set_status(self, status: ModelStatus) -> None:
        """
        设置模型状态（供 ASRInterface 使用）

        Args:
            status: 新状态
        """
        self._status = status

    def _get_device_id(self) -> int:
        """从设备字符串解析设备 ID"""
        return (
            int(self._config.device.split(":")[-1])
            if ":" in self._config.device
            else 0
        )

    def _log_gpu_status(self) -> None:
        """记录 GPU 状态"""
        device_id = self._get_device_id()
        status = self._hardware.get_gpu_memory_status(device_id)

        if status.get("available"):
            logger.info(
                f"GPU 显存状态: 已分配 {status['allocated_gb']:.2f}GB / "
                f"已预留 {status['reserved_gb']:.2f}GB / 总共 {status['total_gb']:.2f}GB"
            )

    def _get_available_vram(self) -> float:
        """
        获取当前可用的 GPU 显存（GB）

        Returns:
            可用显存（GB），如果无 GPU 返回 0
        """
        device_id = self._get_device_id()
        return self._hardware.get_gpu_effective_available_memory_gb(device_id)

    def _determine_model_size(self) -> ModelSize:
        """
        根据配置和可用显存确定模型大小

        Returns:
            最终确定的模型大小
        """
        configured_size = self._config.model_size

        # 如果不是自动模式，直接返回配置的模式
        if configured_size != ModelSize.AUTO:
            logger.info(f"使用配置的模型大小: {MODEL_NAMES[configured_size]}")
            return configured_size

        # 自动模式：根据可用显存选择
        available_vram = self._get_available_vram()
        safety_margin = self._config.auto_quantization_safety_margin
        usable_vram = available_vram - safety_margin

        # 检查是否能运行大模型（即使是 int4 量化）
        min_large_vram = VRAM_REQUIREMENTS[QuantizationMode.INT4]
        min_small_vram = VRAM_REQUIREMENTS_SMALL[QuantizationMode.INT4]

        if usable_vram >= min_large_vram:
            selected_size = ModelSize.LARGE
            logger.info(
                f"显存检测: 可用 {usable_vram:.2f}GB >= {min_large_vram:.2f}GB，选择大模型 ({MODEL_NAMES[selected_size]})"
            )
        elif usable_vram >= min_small_vram:
            selected_size = ModelSize.SMALL
            # 更新模型路径
            self._config.asr_model_path = str(paths.ASR_SMALL_MODEL_DIR)
            logger.warning(
                f"显存受限: 可用 {usable_vram:.2f}GB < {min_large_vram:.2f}GB，自动切换到小模型 ({MODEL_NAMES[selected_size]})"
            )
        else:
            # 显存极度不足，仍尝试小模型
            selected_size = ModelSize.SMALL
            self._config.asr_model_path = str(paths.ASR_SMALL_MODEL_DIR)
            logger.error(
                f"显存极度不足（可用 {usable_vram:.2f}GB < {min_small_vram:.2f}GB），"
                f"强制使用小模型 ({MODEL_NAMES[selected_size]})，可能会失败"
            )

        return selected_size

    def _determine_quantization_mode(self) -> QuantizationMode:
        """
        根据配置和可用显存确定量化模式

        Returns:
            最终确定的量化模式
        """
        configured_mode = self._config.quantization_mode

        # 如果不是自动模式，直接返回配置的模式
        if configured_mode != QuantizationMode.AUTO:
            logger.info(f"使用配置的量化模式: {configured_mode.value}")
            return configured_mode

        # 根据模型大小选择显存需求表
        vram_req = (
            VRAM_REQUIREMENTS_SMALL
            if self._actual_model_size == ModelSize.SMALL
            else VRAM_REQUIREMENTS
        )

        # 自动模式：根据可用显存选择
        available_vram = self._get_available_vram()
        safety_margin = self._config.auto_quantization_safety_margin
        usable_vram = available_vram - safety_margin

        logger.info(
            f"自动量化模式: 可用显存 {available_vram:.2f}GB, 安全余量 {safety_margin:.2f}GB, 可用于模型 {usable_vram:.2f}GB"
        )

        # 按优先级选择量化模式（优先选择精度更高的）
        if usable_vram >= vram_req[QuantizationMode.NONE]:
            selected_mode = QuantizationMode.NONE
            logger.info(f"显存充足，选择 {selected_mode.value} 模式（无量化）")
        elif usable_vram >= vram_req[QuantizationMode.INT8]:
            selected_mode = QuantizationMode.INT8
            logger.warning(f"显存受限，自动切换到 {selected_mode.value} 量化模式")
        elif usable_vram >= vram_req[QuantizationMode.INT4]:
            selected_mode = QuantizationMode.INT4
            logger.warning(f"显存严重受限，自动切换到 {selected_mode.value} 量化模式")
        else:
            # 显存极度不足，仍尝试 int4
            selected_mode = QuantizationMode.INT4
            logger.error(
                f"显存极度不足（可用 {usable_vram:.2f}GB，需要至少 {vram_req[QuantizationMode.INT4]:.2f}GB），"
                f"强制使用 {selected_mode.value} 量化模式，可能会失败"
            )

        return selected_mode

    def _get_lower_quantization_mode(
        self, current_mode: QuantizationMode
    ) -> Optional[QuantizationMode]:
        """
        获取更低精度的量化模式（用于降级）

        Args:
            current_mode: 当前量化模式

        Returns:
            更低精度的模式，如果已是最低则返回 None
        """
        degradation_order = [
            QuantizationMode.NONE,
            QuantizationMode.INT8,
            QuantizationMode.INT4,
        ]

        if current_mode == QuantizationMode.AUTO:
            current_mode = QuantizationMode.NONE

        try:
            current_idx = degradation_order.index(current_mode)
            if current_idx < len(degradation_order) - 1:
                return degradation_order[current_idx + 1]
        except ValueError:
            pass

        return None

    def _build_model_kwargs(self, quantization_mode: QuantizationMode) -> dict:
        """
        构建模型加载参数

        Args:
            quantization_mode: 量化模式

        Returns:
            模型加载参数字典
        """
        base_kwargs = {
            "pretrained_model_name_or_path": self._config.asr_model_path,
            "device_map": self._config.device,
            "max_inference_batch_size": self._config.max_inference_batch_size,
            "max_new_tokens": self._config.max_new_tokens,
            "forced_aligner": self._config.aligner_model_path,
            "forced_aligner_kwargs": dict(
                dtype=self._config.dtype,
                device_map=self._config.device,
            ),
        }

        # 根据量化模式设置参数
        if quantization_mode == QuantizationMode.NONE:
            base_kwargs["dtype"] = self._config.dtype
        elif quantization_mode == QuantizationMode.INT8:
            base_kwargs["load_in_8bit"] = True
        elif quantization_mode == QuantizationMode.INT4:
            base_kwargs["load_in_4bit"] = True

        return base_kwargs

    def _log_loading_params(self, quantization_mode: QuantizationMode) -> None:
        """
        打印模型加载参数

        Args:
            quantization_mode: 量化模式
        """
        logger.debug("=" * 50)
        logger.debug("模型加载参数")
        logger.debug("=" * 50)
        logger.info(f"  [Model] 模型名称: {self.model_name}")
        logger.debug(f"  ASR 模型路径: {self._config.asr_model_path}")
        logger.debug(f"  对齐器模型路径: {self._config.aligner_model_path}")
        logger.debug(f"  设备: {self._config.device}")
        logger.debug(f"  量化模式: {quantization_mode.value}")

        if quantization_mode == QuantizationMode.NONE:
            logger.debug(f"  数据类型: {self._config.dtype}")
        elif quantization_mode == QuantizationMode.INT8:
            logger.debug("  数据类型: 8-bit 量化")
        elif quantization_mode == QuantizationMode.INT4:
            logger.debug("  数据类型: 4-bit 量化")

        logger.debug(f"  最大推理批大小: {self._config.max_inference_batch_size}")
        logger.debug(f"  最大生成 tokens: {self._config.max_new_tokens}")
        logger.debug("=" * 50)
