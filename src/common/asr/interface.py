"""
ASR Interface Module
提供语音识别和强制对齐接口

职责:
- 转录和对齐功能
- 音频分段处理
- 使用 ASRModelHolder 提供的模型进行推理
"""

import math
import time
import torch
from dataclasses import dataclass
from typing import List, Optional, Union
from enum import Enum

from tqdm import tqdm
from loguru import logger

from src.core.vo import TimeStampItem, TranscriptionResult, AlignmentResult
from src.common.media_handler import MediaHandler, AudioData
from src.common.asr.model_holder import (
    ASRModelHolder,
    ModelStatus,
    QuantizationMode,
)


class Language(Enum):
    """语言类型枚举"""

    AUTO = "Auto"  # 自动检测语言
    CHINESE = "Chinese"
    ENGLISH = "English"
    CANTONESE = "Cantonese"
    FRENCH = "French"
    GERMAN = "German"
    ITALIAN = "Italian"
    JAPANESE = "Japanese"
    KOREAN = "Korean"
    PORTUGUESE = "Portuguese"
    RUSSIAN = "Russian"
    SPANISH = "Spanish"


@dataclass
class ASRConfig:
    """ASR 推理配置（不包含模型加载配置）"""

    segment_duration: float = 15.0  # 分段时长（秒）
    sample_rate: int = 16000
    # 算力限制相关配置
    # 推理间隔延迟（秒），在每个段推理后暂停，让 GPU 有时间处理其他任务
    inference_delay: float = 0.0
    # 是否启用低优先级模式（减少对其他 GPU 任务的影响）
    low_priority_mode: bool = False

    @property
    def max_new_tokens(self) -> int:
        """根据分段时长计算最大生成 token 数（1秒 = 18 token）"""
        return math.ceil(self.segment_duration * 18)


class ASRInterface:
    """
    ASR 接口类

    提供语音识别和强制对齐功能，使用 ASRModelHolder 提供的模型进行推理。
    此类不负责模型加载/卸载，这些由 ASRModelHolder 管理。

    使用示例::

        # 使用 ASRModelHolder 单例
        holder = ASRModelHolder()
        holder.load()

        # 创建接口并转录
        asr = ASRInterface(model_holder=holder)
        result = asr.transcribe("audio.wav")
        print(result.text)

        # 对齐
        align_result = asr.align("audio.wav", "文本内容")
    """

    def __init__(
        self,
        model_holder: ASRModelHolder,
        config: Optional[ASRConfig] = None,
    ):
        """
        初始化 ASR 接口

        Args:
            model_holder: 模型容器单例
            config: ASR 推理配置
        """
        self._model_holder = model_holder
        self._config = config or ASRConfig()
        self._media_handler = MediaHandler(default_sample_rate=self._config.sample_rate)
        self._last_audio: Optional[AudioData] = None

        # 应用低优先级模式
        if self._config.low_priority_mode:
            self._apply_low_priority_mode()

        logger.debug("ASRInterface 初始化完成")

    @property
    def config(self) -> ASRConfig:
        """获取推理配置"""
        return self._config

    @property
    def model_holder(self) -> ASRModelHolder:
        """获取模型容器"""
        return self._model_holder

    @property
    def is_ready(self) -> bool:
        """检查模型是否就绪"""
        return self._model_holder.is_ready

    @property
    def media_handler(self) -> MediaHandler:
        """获取媒体处理器实例"""
        return self._media_handler

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

        Raises:
            RuntimeError: 模型未加载时抛出
        """
        if not self._model_holder.is_ready:
            raise RuntimeError("模型未加载，请先调用 model_holder.load()")

        model = self._model_holder.model
        if model is None:
            raise RuntimeError("模型未加载")

        self._model_holder.set_status(ModelStatus.PROCESSING)

        try:
            # 加载音频
            if isinstance(audio_input, str):
                logger.info(f"开始转录: {audio_input}")
                audio = self._media_handler.load(audio_input)
            else:
                logger.info(f"开始转录: AudioData ({audio_input.duration:.1f}秒)")
                audio = audio_input

            # 缓存音频
            self._last_audio = audio
            total_duration = audio.duration

            # 分段处理
            segments = self._media_handler.segment_with_tuples(
                audio, self._config.segment_duration
            )

            # 逐段处理
            all_texts = []
            all_timestamps = []
            time_offset = 0.0
            detected_language = None

            iterator = tqdm(segments, desc="转录进度") if show_progress else segments

            for segment in iterator:
                try:
                    result = model.transcribe(
                        audio=segment, return_time_stamps=return_time_stamps
                    )
                except torch.cuda.OutOfMemoryError as oom_error:
                    # 推理时 OOM，尝试降级量化模式
                    if self._try_quantization_fallback():
                        # 重新开始转录
                        return self.transcribe(
                            audio_input, return_time_stamps, show_progress
                        )
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
                        all_timestamps.append(
                            TimeStampItem(
                                text=item.text,
                                start_time=item.start_time + time_offset,
                                end_time=item.end_time + time_offset,
                            )
                        )

                time_offset += self._config.segment_duration

                # 算力限制：推理后添加延迟
                if self._config.inference_delay > 0:
                    torch.cuda.synchronize()
                    time.sleep(self._config.inference_delay)

            self._model_holder.set_status(ModelStatus.READY)

            result = TranscriptionResult(
                language=detected_language or "unknown",
                text="".join(all_texts),
                time_stamps=all_timestamps if all_timestamps else None,
                duration=total_duration,
            )

            logger.success(
                f"转录完成: 语言={result.language}, 时长={result.duration:.1f}秒, "
                f"文字长度={len(result.text)}"
            )

            return result

        except Exception as e:
            self._model_holder.set_status(ModelStatus.ERROR)
            logger.error(f"转录失败: {e}")
            raise

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
            logger.info(f"处理文件 {i + 1}/{len(audio_paths)}: {audio_path}")
            result = self.transcribe(audio_path, return_time_stamps, show_progress)
            results.append(result)

        logger.success(f"批量转录完成: 共 {len(results)} 个文件")
        return results

    def align(
        self,
        audio_input: Union[str, AudioData],
        text: str,
        language: Union[Language, List[Language]] = Language.CHINESE,
    ) -> AlignmentResult:
        """
        对齐音频和文本，返回时间戳

        Args:
            audio_input: 音频文件路径或 AudioData 对象
            text: 需要对齐的文本内容
            language: 语言类型枚举或语言列表

        Returns:
            对齐结果

        Raises:
            RuntimeError: 模型未加载或对齐器不可用时抛出
            ValueError: 文本为空时抛出
        """
        if not text or not text.strip():
            raise ValueError("对齐文本不能为空")

        if not self._model_holder.is_ready:
            raise RuntimeError("模型未加载，请先调用 model_holder.load()")

        forced_aligner = self._model_holder.forced_aligner
        if forced_aligner is None:
            raise RuntimeError("强制对齐器未加载")

        self._model_holder.set_status(ModelStatus.PROCESSING)

        try:
            # 加载音频
            if isinstance(audio_input, str):
                logger.info(f"开始对齐: {audio_input}")
                audio = self._media_handler.load(audio_input)
            else:
                logger.info(f"开始对齐: AudioData ({audio_input.duration:.1f}秒)")
                audio = audio_input

            # 缓存音频
            self._last_audio = audio
            audio_duration = audio.duration

            # 准备音频数据格式
            audio_tuple = (audio.data, audio.sample_rate)

            # 转换语言参数
            language_param = self._convert_language_to_api_format(language)

            # 调用对齐器
            # 如果语言为 None（自动检测），使用默认语言
            align_results = forced_aligner.align(
                audio=audio_tuple,
                text=text,
                language=language_param if language_param is not None else "Chinese",
            )

            # 转换结果格式
            time_stamps: List[TimeStampItem] = []
            if align_results and len(align_results) > 0:
                for item in align_results[0]:
                    time_stamps.append(
                        TimeStampItem(
                            text=item.text,
                            start_time=item.start_time,
                            end_time=item.end_time,
                        )
                    )

            self._model_holder.set_status(ModelStatus.READY)

            # 格式化语言信息
            language_display = self._format_language_for_display(language)

            result = AlignmentResult(
                text=text,
                language=language_display,
                time_stamps=time_stamps,
                audio_duration=audio_duration,
            )

            logger.success(
                f"对齐完成: 语言={language_display}, "
                f"字/词数={result.word_count}, "
                f"音频时长={audio_duration:.1f}秒"
            )

            return result

        except Exception as e:
            self._model_holder.set_status(ModelStatus.ERROR)
            logger.error(f"对齐失败: {e}")
            raise

    def align_batch(
        self,
        items: List[tuple],
        language: Union[Language, List[Language]] = Language.CHINESE,
    ) -> List[AlignmentResult]:
        """
        批量对齐多个音频-文本对

        Args:
            items: 音频-文本对列表，每个元素为 (audio_input, text) 元组
            language: 语言类型枚举或语言列表

        Returns:
            对齐结果列表
        """
        results: List[AlignmentResult] = []

        for i, (audio_input, text) in enumerate(items):
            logger.info(f"对齐进度 {i + 1}/{len(items)}")
            result = self.align(audio_input, text, language)
            results.append(result)

        logger.success(f"批量对齐完成: 共 {len(results)} 个文件")
        return results

    def get_last_audio(self) -> Optional[AudioData]:
        """获取最后转录/对齐的音频数据"""
        return self._last_audio

    def _try_quantization_fallback(self) -> bool:
        """
        尝试降级量化模式

        Returns:
            是否成功降级
        """
        current_mode = (
            self._model_holder.actual_quantization_mode or QuantizationMode.NONE
        )

        # 获取更低精度的模式
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
                lower_mode = degradation_order[current_idx + 1]
                logger.warning(
                    f"推理时显存不足，尝试降级到 {lower_mode.value} 量化模式..."
                )
                # 更新配置并重新加载
                self._model_holder.config.quantization_mode = lower_mode
                self._model_holder.reload()
                return True
        except ValueError:
            pass

        return False

    def _convert_language_to_api_format(
        self, language: Union[Language, List[Language]]
    ) -> Union[str, List[str], None]:
        """转换语言参数为 API 格式"""
        if isinstance(language, Language):
            if language == Language.AUTO:
                return None
            return language.value
        elif isinstance(language, list):
            if Language.AUTO in language:
                return None
            return [lang.value for lang in language]
        else:
            raise TypeError(f"不支持的语言类型: {type(language)}")

    def _format_language_for_display(
        self, language: Union[Language, List[Language]]
    ) -> str:
        """格式化语言参数用于显示"""
        if isinstance(language, Language):
            return language.value
        elif isinstance(language, list):
            return ", ".join(lang.value for lang in language)
        else:
            return str(language)

    def _apply_low_priority_mode(self) -> None:
        """应用低优先级模式"""
        import platform
        import os

        system = platform.system()

        try:
            if system == "Windows":
                import ctypes

                BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.GetCurrentProcess()
                kernel32.SetPriorityClass(handle, BELOW_NORMAL_PRIORITY_CLASS)
                logger.info("已启用低优先级模式：进程优先级设置为 BELOW_NORMAL")

            elif system in ("Linux", "Darwin"):
                os.nice(10)  # type: ignore[attr-defined]
                logger.info("已启用低优先级模式：nice 值设置为 10")

        except Exception as e:
            logger.warning(f"无法设置低优先级模式: {e}")
