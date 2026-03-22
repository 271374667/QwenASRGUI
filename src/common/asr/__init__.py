"""
ASR 模块
提供语音识别功能的分层架构实现

模块结构:
- model_holder: 模型容器单例，管理模型生命周期
- interface: ASR 接口，提供转录和对齐功能
- service: ASR 服务单例，提供 Qt 集成和同步服务支持

使用示例::

    # 方式 1: 使用 ASRService（推荐，适合 GUI 场景）
    from src.common.asr import ASRService

    service = ASRService()
    service.signals.loading_finished.connect(on_loaded)
    service.load_model()
    result = service.transcribe("audio.wav")

    # 方式 2: 使用分离的 ModelHolder 和 Interface（适合非 Qt 场景）
    from src.common.asr import ASRModelHolder, ASRInterface

    holder = ASRModelHolder()
    holder.load()
    asr = ASRInterface(model_holder=holder)
    result = asr.transcribe("audio.wav")
"""

from src.common.asr.model_holder import (
    ASRModelHolder,
    ModelConfig,
    ModelStatus,
    QuantizationMode,
    ModelSize,
    VRAM_REQUIREMENTS,
    VRAM_REQUIREMENTS_SMALL,
    MODEL_NAMES,
)
from src.common.asr.interface import (
    ASRInterface,
    ASRConfig,
    Language,
)
from src.common.asr.service import (
    ASRService,
    ASRServiceSignals,
)

__all__ = [
    # model_holder
    "ASRModelHolder",
    "ModelConfig",
    "ModelStatus",
    "QuantizationMode",
    "ModelSize",
    "VRAM_REQUIREMENTS",
    "VRAM_REQUIREMENTS_SMALL",
    "MODEL_NAMES",
    # interface
    "ASRInterface",
    "ASRConfig",
    "Language",
    # service
    "ASRService",
    "ASRServiceSignals",
]
