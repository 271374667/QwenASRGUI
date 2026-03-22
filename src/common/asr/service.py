"""
ASR Service Module
服务层单例，提供 Qt 信号槽支持

职责:
- 封装 ASRModelHolder 和 ASRInterface
- 提供 Qt 信号槽（模型加载进度、状态变更通知）
- 提供简化的同步 API
"""

from typing import List, Optional, Union

from loguru import logger
from PySide6.QtCore import QObject, Signal

from src.core.vo import TranscriptionResult, AlignmentResult
from src.common.media_handler import AudioData
from src.common.asr.model_holder import (
    ASRModelHolder,
    ModelConfig,
    ModelStatus,
    QuantizationMode,
    ModelSize,
)
from src.common.asr.interface import (
    ASRInterface,
    ASRConfig,
    Language,
)
from src.utils.singleton import singleton


class ASRServiceSignals(QObject):
    """ASR 服务信号集合"""

    # 模型状态变更信号
    status_changed = Signal(ModelStatus)

    # 模型加载进度信号 (0-100)
    loading_progress = Signal(int)

    # 模型加载完成信号 (success: bool, message: str)
    loading_finished = Signal(bool, str)

    # 模型卸载完成信号
    unloading_finished = Signal()

    # 转录进度信号 (current, total)
    transcribe_progress = Signal(int, int)

    # 转录完成信号 (result: TranscriptionResult or None, error: str or None)
    transcribe_finished = Signal(object, str)

    # 对齐完成信号 (result: AlignmentResult or None, error: str or None)
    align_finished = Signal(object, str)

    # 错误信号
    error_occurred = Signal(str)


@singleton
class ASRService(QObject):
    """
    ASR 服务单例

    提供 Qt 信号槽支持，封装 ASRModelHolder 和 ASRInterface。

    特性:
    - Qt 信号槽：status_changed, loading_progress, loading_finished 等
    - 同步调用：load_model(), transcribe(), align() 等
    - 简化的 API：无需手动管理 ModelHolder 和 Interface

    使用示例::

        service = ASRService()
        service.signals.loading_finished.connect(on_loaded)
        service.load_model()

        result = service.transcribe("audio.wav")
    """

    def __init__(self, parent: Optional[QObject] = None):
        """初始化 ASR 服务"""
        super().__init__(parent)

        self._signals = ASRServiceSignals()
        self._model_holder = ASRModelHolder()
        self._interface: Optional[ASRInterface] = None
        self._last_status = ModelStatus.NOT_LOADED

        logger.info("ASRService 初始化完成")

    @property
    def signals(self) -> ASRServiceSignals:
        """获取信号对象"""
        return self._signals

    @property
    def model_holder(self) -> ASRModelHolder:
        """获取模型容器"""
        return self._model_holder

    @property
    def interface(self) -> Optional[ASRInterface]:
        """获取 ASR 接口"""
        return self._interface

    @property
    def status(self) -> ModelStatus:
        """获取当前模型状态"""
        return self._model_holder.status

    @property
    def is_ready(self) -> bool:
        """检查模型是否就绪"""
        return self._model_holder.is_ready

    @property
    def model_name(self) -> str:
        """获取当前使用的模型名称"""
        return self._model_holder.model_name

    @property
    def actual_quantization_mode(self) -> Optional[QuantizationMode]:
        """获取实际使用的量化模式"""
        return self._model_holder.actual_quantization_mode

    @property
    def actual_model_size(self) -> Optional[ModelSize]:
        """获取实际使用的模型大小"""
        return self._model_holder.actual_model_size

    # ==================== 同步方法 ====================

    def load_model(self, config: Optional[ModelConfig] = None) -> bool:
        """
        加载模型（同步方式）

        Args:
            config: 可选的模型配置

        Returns:
            是否加载成功
        """
        try:
            self._emit_status_change(ModelStatus.LOADING)
            self._signals.loading_progress.emit(10)

            self._model_holder.load(config)

            self._signals.loading_progress.emit(90)

            # 创建接口
            self._interface = ASRInterface(model_holder=self._model_holder)

            self._signals.loading_progress.emit(100)
            self._emit_status_change(ModelStatus.READY)
            self._signals.loading_finished.emit(True, "模型加载成功")

            logger.success(f"模型加载成功: {self.model_name}")
            return True

        except Exception as e:
            error_msg = f"模型加载失败: {e}"
            logger.error(error_msg)
            self._emit_status_change(ModelStatus.ERROR)
            self._signals.loading_finished.emit(False, error_msg)
            self._signals.error_occurred.emit(error_msg)
            return False

    def unload_model(self) -> None:
        """卸载模型（同步方式）"""
        self._model_holder.unload()
        self._interface = None
        self._emit_status_change(ModelStatus.NOT_LOADED)
        self._signals.unloading_finished.emit()
        logger.info("模型已卸载")

    def reload_model(self, config: Optional[ModelConfig] = None) -> bool:
        """
        重新加载模型

        Args:
            config: 可选的新配置

        Returns:
            是否加载成功
        """
        self.unload_model()
        return self.load_model(config)

    def transcribe(
        self,
        audio_input: Union[str, AudioData],
        return_time_stamps: bool = True,
        show_progress: bool = False,
    ) -> Optional[TranscriptionResult]:
        """
        转录音频（同步方式）

        Args:
            audio_input: 音频文件路径或 AudioData 对象
            return_time_stamps: 是否返回时间戳
            show_progress: 是否在控制台显示进度

        Returns:
            转录结果，失败时返回 None
        """
        if not self.is_ready or self._interface is None:
            error_msg = "模型未加载"
            self._signals.error_occurred.emit(error_msg)
            self._signals.transcribe_finished.emit(None, error_msg)
            return None

        try:
            self._emit_status_change(ModelStatus.PROCESSING)
            result = self._interface.transcribe(
                audio_input, return_time_stamps, show_progress
            )
            self._emit_status_change(ModelStatus.READY)
            self._signals.transcribe_finished.emit(result, "")
            return result

        except Exception as e:
            error_msg = f"转录失败: {e}"
            logger.error(error_msg)
            self._emit_status_change(ModelStatus.ERROR)
            self._signals.transcribe_finished.emit(None, error_msg)
            self._signals.error_occurred.emit(error_msg)
            return None

    def align(
        self,
        audio_input: Union[str, AudioData],
        text: str,
        language: Union[Language, List[Language]] = Language.CHINESE,
    ) -> Optional[AlignmentResult]:
        """
        对齐音频和文本（同步方式）

        Args:
            audio_input: 音频文件路径或 AudioData 对象
            text: 需要对齐的文本
            language: 语言类型

        Returns:
            对齐结果，失败时返回 None
        """
        if not self.is_ready or self._interface is None:
            error_msg = "模型未加载"
            self._signals.error_occurred.emit(error_msg)
            self._signals.align_finished.emit(None, error_msg)
            return None

        try:
            self._emit_status_change(ModelStatus.PROCESSING)
            result = self._interface.align(audio_input, text, language)
            self._emit_status_change(ModelStatus.READY)
            self._signals.align_finished.emit(result, "")
            return result

        except Exception as e:
            error_msg = f"对齐失败: {e}"
            logger.error(error_msg)
            self._emit_status_change(ModelStatus.ERROR)
            self._signals.align_finished.emit(None, error_msg)
            self._signals.error_occurred.emit(error_msg)
            return None

    # ==================== 辅助方法 ====================

    def configure_interface(self, config: ASRConfig) -> None:
        """
        配置 ASR 接口参数

        Args:
            config: 推理配置
        """
        if self._interface is not None:
            self._interface = ASRInterface(
                model_holder=self._model_holder, config=config
            )
            logger.info("ASR 接口配置已更新")

    def get_last_audio(self) -> Optional[AudioData]:
        """获取最后转录/对齐的音频数据"""
        if self._interface is not None:
            return self._interface.get_last_audio()
        return None

    def _emit_status_change(self, status: ModelStatus) -> None:
        """发送状态变更信号"""
        if status != self._last_status:
            self._last_status = status
            self._signals.status_changed.emit(status)
