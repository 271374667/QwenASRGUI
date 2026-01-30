"""
ASR Interface Module
提供面向对象的语音识别接口
"""

import torch
import warnings
from dataclasses import dataclass
from typing import List, Optional, Union
from enum import Enum

from tqdm import tqdm
from loguru import logger
from transformers import logging as transformers_logging
from qwen_asr import Qwen3ASRModel
from src.core import paths
from src.core.vo import TimeStampItem, TranscriptionResult
from src.common.media_handler import MediaHandler, AudioData
from src.utils.hardware import Hardware


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
    NONE = "fp16"      # 无量化，使用 fp16
    INT8 = "int8"      # 8-bit 量化
    INT4 = "int4"      # 4-bit 量化
    AUTO = "auto"      # 自动选择


# 不同量化模式下模型的预估显存需求（GB）
# 基于 Qwen3-ASR-1.7B + Forced Aligner 模型估算
# 注意：KV cache 和激活值在推理时仍使用 fp16，需要额外显存
VRAM_REQUIREMENTS = {
    QuantizationMode.NONE: 6.0,   # fp16: ~3.4GB ASR + ~1.2GB Aligner + 1.4GB 推理开销
    QuantizationMode.INT8: 4.5,   # int8: ~1.7GB ASR + ~1.2GB Aligner + 1.6GB 推理开销(KV cache仍fp16)
    QuantizationMode.INT4: 3.5,   # int4: ~0.85GB ASR + ~1.2GB Aligner + 1.45GB 推理开销
}


@dataclass
class ASRConfig:
    """ASR 配置"""
    asr_model_path: str = str(paths.ASR_MODEL_DIR)
    aligner_model_path: str = str(paths.FORCED_ALIGNER_MODEL_DIR)
    dtype: torch.dtype = torch.float16
    device: str = "cuda:0"
    max_inference_batch_size: int = 32
    max_new_tokens: int = 256
    segment_duration: float = 15.0  # 分段时长（秒）
    sample_rate: int = 16000
    # 量化相关配置
    quantization_mode: QuantizationMode = QuantizationMode.AUTO
    # 自动量化时的安全余量（GB），确保有足够空间进行推理
    auto_quantization_safety_margin: float = 0.5


class ASRInterface:
    """
    ASR 接口类
    提供语音识别功能的统一接口，封装模型加载、音频分段与转录流程。

    用法概览：
    - 创建实例：可传入 ASRConfig 指定模型路径、设备、批大小等
    - 加载模型：`load_model()`；也可直接调用 `transcribe()` 自动加载
    - 转录：`transcribe()` 单文件，`transcribe_batch()` 多文件
    - 释放资源：`unload_model()` 主动释放显存
    - 上下文管理：`with ASRInterface(...) as asr: ...` 自动加载与卸载

    公开属性：
    - status: 当前模型状态（ModelStatus）
    - is_ready: 模型是否就绪

    公开方法：
    - load_model(): 显式加载 ASR 模型
    - unload_model(): 卸载模型并释放显存
    - transcribe(audio_path, return_time_stamps=True, show_progress=True): 转录单个音频文件
    - transcribe_batch(audio_paths, return_time_stamps=True, show_progress=True): 批量转录多个音频文件

    典型示例：
        asr = ASRInterface()
        result = asr.transcribe("demo.wav")
        print(result.text)

        with ASRInterface() as asr:
            results = asr.transcribe_batch(["a.wav", "b.wav"])
            for r in results:
                print(r.language, r.duration)
    """
    
    def __init__(self, config: Optional[ASRConfig] = None):
        """
        初始化 ASR 接口
        
        Args:
            config: ASR 配置，如果为 None 则使用默认配置
        """
        self.config = config or ASRConfig()
        self._model: Optional[Qwen3ASRModel] = None
        self._status = ModelStatus.NOT_LOADED
        self._media_handler = MediaHandler(default_sample_rate=self.config.sample_rate)
        self._hardware = Hardware()  # 硬件信息检测器
        self._last_audio: Optional[AudioData] = None  # 缓存最后加载的音频
        self._actual_quantization_mode: Optional[QuantizationMode] = None  # 实际使用的量化模式
        
        logger.info("ASR 接口初始化完成")
        logger.debug(f"配置: ASR模型={self.config.asr_model_path}, 对齐器={self.config.aligner_model_path}")
    
    @property
    def status(self) -> ModelStatus:
        """获取当前模型状态"""
        return self._status
    
    @property
    def is_ready(self) -> bool:
        """检查模型是否就绪"""
        return self._status == ModelStatus.READY
    
    @property
    def actual_quantization_mode(self) -> Optional[QuantizationMode]:
        """获取实际使用的量化模式"""
        return self._actual_quantization_mode
    
    def load_model(self) -> None:
        """加载模型（支持自动量化降级）"""
        if self._status == ModelStatus.READY:
            logger.warning("模型已加载，跳过重复加载")
            return
        
        self._status = ModelStatus.LOADING
        logger.info("开始加载 ASR 模型...")
        
        # 确定量化模式
        quantization_mode = self._determine_quantization_mode()
        self._actual_quantization_mode = quantization_mode
        
        # 打印加载参数
        self._log_loading_params(quantization_mode)
        
        try:
            # 构建模型加载参数
            model_kwargs = self._build_model_kwargs(quantization_mode)
            
            self._model = Qwen3ASRModel.from_pretrained(**model_kwargs)
            self._status = ModelStatus.READY
            logger.success("模型加载完成")
            self._log_gpu_status()
            
        except torch.cuda.OutOfMemoryError as e:
            # 如果 OOM 且还能降级，尝试降级
            lower_mode = self._get_lower_quantization_mode(quantization_mode)
            if lower_mode is not None:
                logger.warning(f"显存不足，尝试降级到 {lower_mode.value} 量化模式...")
                self._status = ModelStatus.NOT_LOADED
                torch.cuda.empty_cache()
                # 更新配置并重试
                self.config.quantization_mode = lower_mode
                self.load_model()
            else:
                self._status = ModelStatus.ERROR
                logger.error(f"模型加载失败（显存不足）: {e}")
                raise
        except Exception as e:
            self._status = ModelStatus.ERROR
            logger.error(f"模型加载失败: {e}")
            raise
    
    def unload_model(self) -> None:
        """卸载模型释放显存"""
        if self._model is not None:
            del self._model
            self._model = None
            torch.cuda.empty_cache()
            self._status = ModelStatus.NOT_LOADED
            logger.info("模型已卸载，显存已释放")
    
    def transcribe(
        self,
        audio_input: Union[str, AudioData],
        return_time_stamps: bool = True,
        show_progress: bool = True,
    ) -> TranscriptionResult:
        """
        转录音频文件
        
        Args:
            audio_input: 音频文件路径或 AudioData 对象
            return_time_stamps: 是否返回时间戳
            show_progress: 是否显示进度条
            
        Returns:
            转录结果
        """
        if not self.is_ready:
            logger.warning("模型未加载，正在自动加载...")
            self.load_model()
        
        if self._model is None:
            raise RuntimeError("模型未加载，无法进行转录")
        
        self._status = ModelStatus.PROCESSING
        
        try:
            # 加载音频（支持路径或 AudioData）
            if isinstance(audio_input, str):
                logger.info(f"开始转录: {audio_input}")
                audio = self._media_handler.load(audio_input)
            else:
                logger.info(f"开始转录: AudioData ({audio_input.duration:.1f}秒)")
                audio = audio_input
            
            # 缓存音频供后续使用（如 VAD）
            self._last_audio = audio
            total_duration = audio.duration
            
            # 分段处理
            segments = self._media_handler.segment_with_tuples(audio, self.config.segment_duration)
            
            # 逐段处理
            all_texts = []
            all_timestamps = []
            time_offset = 0.0
            detected_language = None
            
            iterator = tqdm(segments, desc="转录进度") if show_progress else segments
            
            for segment in iterator:
                try:
                    result = self._model.transcribe(
                        audio=segment,
                        return_time_stamps=return_time_stamps
                    )
                except torch.cuda.OutOfMemoryError as oom_error:
                    # 推理时 OOM，尝试降级量化模式
                    current_mode = self._actual_quantization_mode or QuantizationMode.NONE
                    lower_mode = self._get_lower_quantization_mode(current_mode)
                    if lower_mode is not None:
                        logger.warning(
                            f"推理时显存不足，尝试降级到 {lower_mode.value} 量化模式并重新加载模型..."
                        )
                        # 卸载当前模型
                        self.unload_model()
                        # 更新配置并重新加载
                        self.config.quantization_mode = lower_mode
                        self.load_model()
                        # 重新开始转录（递归调用）
                        return self.transcribe(audio_input, return_time_stamps, show_progress)
                    else:
                        logger.error("推理时显存不足，已是最低精度模式，无法继续降级")
                        raise oom_error
                
                segment_result = result[0]
                all_texts.append(segment_result.text)
                
                if detected_language is None:
                    detected_language = segment_result.language
                
                # 处理时间戳
                if return_time_stamps and segment_result.time_stamps:
                    for item in segment_result.time_stamps:
                        all_timestamps.append(TimeStampItem(
                            text=item.text,
                            start_time=item.start_time + time_offset,
                            end_time=item.end_time + time_offset
                        ))
                
                time_offset += self.config.segment_duration
            
            self._status = ModelStatus.READY
            
            result = TranscriptionResult(
                language=detected_language or "unknown",
                text="".join(all_texts),
                time_stamps=all_timestamps if all_timestamps else None,
                duration=total_duration
            )
            
            logger.success(f"转录完成: 语言={result.language}, 时长={result.duration:.1f}秒, 文字长度={len(result.text)}")
            self._log_gpu_status()
            
            return result
            
        except Exception as e:
            self._status = ModelStatus.ERROR
            logger.error(f"转录失败: {e}")
            raise
    
    def get_last_audio(self) -> Optional[AudioData]:
        """
        获取最后转录的音频数据
        
        用于 VAD 等后续处理，避免重复加载音频
        
        Returns:
            AudioData 对象，如果未转录过则返回 None
        """
        return self._last_audio
    
    @property
    def media_handler(self) -> MediaHandler:
        """获取媒体处理器实例"""
        return self._media_handler

    def transcribe_batch(
        self,
        audio_paths: List[str],
        return_time_stamps: bool = True,
        show_progress: bool = True,
    ) -> List[TranscriptionResult]:
        """
        批量转录多个音频文件
        
        Args:
            audio_paths: 音频文件路径列表
            return_time_stamps: 是否返回时间戳
            show_progress: 是否显示进度条
            
        Returns:
            转录结果列表
        """
        results = []
        
        for i, audio_path in enumerate(audio_paths):
            logger.info(f"处理文件 {i+1}/{len(audio_paths)}: {audio_path}")
            result = self.transcribe(audio_path, return_time_stamps, show_progress)
            results.append(result)
        
        logger.success(f"批量转录完成: 共 {len(results)} 个文件")
        return results
    
    def __enter__(self):
        """上下文管理器入口"""
        self.load_model()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.unload_model()
        self._media_handler.clear_cache()
        return False

    def _get_device_id(self) -> int:
        """从设备字符串解析设备 ID"""
        return int(self.config.device.split(":")[-1]) if ":" in self.config.device else 0

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

    def _determine_quantization_mode(self) -> QuantizationMode:
        """
        根据配置和可用显存确定量化模式
        
        Returns:
            最终确定的量化模式
        """
        configured_mode = self.config.quantization_mode
        
        # 如果不是自动模式，直接返回配置的模式
        if configured_mode != QuantizationMode.AUTO:
            logger.info(f"使用配置的量化模式: {configured_mode.value}")
            return configured_mode
        
        # 自动模式：根据可用显存选择
        available_vram = self._get_available_vram()
        safety_margin = self.config.auto_quantization_safety_margin
        usable_vram = available_vram - safety_margin
        
        logger.info(f"自动量化模式: 可用显存 {available_vram:.2f}GB, 安全余量 {safety_margin:.2f}GB, 可用于模型 {usable_vram:.2f}GB")
        
        # 按优先级选择量化模式（优先选择精度更高的）
        if usable_vram >= VRAM_REQUIREMENTS[QuantizationMode.NONE]:
            selected_mode = QuantizationMode.NONE
            logger.info(f"显存充足，选择 {selected_mode.value} 模式（无量化）")
        elif usable_vram >= VRAM_REQUIREMENTS[QuantizationMode.INT8]:
            selected_mode = QuantizationMode.INT8
            logger.warning(f"显存受限，自动切换到 {selected_mode.value} 量化模式")
        elif usable_vram >= VRAM_REQUIREMENTS[QuantizationMode.INT4]:
            selected_mode = QuantizationMode.INT4
            logger.warning(f"显存严重受限，自动切换到 {selected_mode.value} 量化模式")
        else:
            # 显存极度不足，仍尝试 int4
            selected_mode = QuantizationMode.INT4
            logger.error(
                f"显存极度不足（可用 {usable_vram:.2f}GB，需要至少 {VRAM_REQUIREMENTS[QuantizationMode.INT4]:.2f}GB），"
                f"强制使用 {selected_mode.value} 量化模式，可能会失败"
            )
        
        return selected_mode

    def _get_lower_quantization_mode(self, current_mode: QuantizationMode) -> Optional[QuantizationMode]:
        """
        获取更低精度的量化模式（用于降级）
        
        Args:
            current_mode: 当前量化模式
            
        Returns:
            更低精度的模式，如果已是最低则返回 None
        """
        degradation_order = [QuantizationMode.NONE, QuantizationMode.INT8, QuantizationMode.INT4]
        
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
            "pretrained_model_name_or_path": self.config.asr_model_path,
            "device_map": self.config.device,
            "max_inference_batch_size": self.config.max_inference_batch_size,
            "max_new_tokens": self.config.max_new_tokens,
            "forced_aligner": self.config.aligner_model_path,
            "forced_aligner_kwargs": dict(
                dtype=self.config.dtype,
                device_map=self.config.device,
            ),
        }
        
        # 根据量化模式设置参数
        if quantization_mode == QuantizationMode.NONE:
            base_kwargs["dtype"] = self.config.dtype
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
        logger.info("=" * 50)
        logger.info("模型加载参数")
        logger.info("=" * 50)
        logger.info(f"  ASR 模型路径: {self.config.asr_model_path}")
        logger.info(f"  对齐器模型路径: {self.config.aligner_model_path}")
        logger.info(f"  设备: {self.config.device}")
        logger.info(f"  量化模式: {quantization_mode.value}")
        
        if quantization_mode == QuantizationMode.NONE:
            logger.info(f"  数据类型: {self.config.dtype}")
        elif quantization_mode == QuantizationMode.INT8:
            logger.info("  数据类型: 8-bit 量化")
        elif quantization_mode == QuantizationMode.INT4:
            logger.info("  数据类型: 4-bit 量化")
        
        logger.info(f"  最大推理批大小: {self.config.max_inference_batch_size}")
        logger.info(f"  最大生成 tokens: {self.config.max_new_tokens}")
        logger.info(f"  分段时长: {self.config.segment_duration}秒")
        logger.info(f"  采样率: {self.config.sample_rate}Hz")
        logger.info("=" * 50)
