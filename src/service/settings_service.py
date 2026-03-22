"""应用设置服务。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, Property, QSettings, Signal, Slot

from src.utils.hardware import Hardware


DEFAULT_SETTINGS: Dict[str, Any] = {
    "modelSize": "auto",
    "quantizationMode": "auto",
    "device": "auto",
    "segmentDuration": 15.0,
    "lowPriorityMode": False,
    "inferenceDelay": 0.0,
    "enableMemoryLimit": False,
    "systemMemoryPercent": 85.0,
    "gpuMemoryPercent": 85.0,
    "gapDetectionMethod": "silero_vad",
    "maxCharsPerLine": 20,
    "maxDurationPerLine": 5.0,
}


class SettingsService(QObject):
    """管理 GUI 运行配置与持久化设置。

    该服务负责维护模型加载、推理、字幕分行和资源限制相关配置，并使用
    `QSettings` 进行本地持久化。QML 页面通过 `settings` 与若干选项列表
    访问和修改配置。

    Attributes:
        settings_changed: 配置变化通知。
        options_changed: 选项列表变化通知。

    Example:
        基本用法::

            settings_service = SettingsService()
            settings_service.update_setting("modelSize", "small")
            model_config = settings_service.build_model_config()

    Note:
        设置更新会立即保存到本地，下次启动时自动恢复。
    """

    settings_changed = Signal()
    options_changed = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        """初始化设置服务。"""
        super().__init__(parent)
        self._storage = QSettings("QwenASRGUI", "QwenASRGUI")
        self._hardware = Hardware()
        self._settings: Dict[str, Any] = dict(DEFAULT_SETTINGS)
        self._load_settings()

    @Property("QVariantMap", notify=settings_changed)
    def settings(self) -> Dict[str, Any]:
        """返回 QML 可绑定的设置字典。"""
        return dict(self._settings)

    @Property("QVariantList", notify=options_changed)
    def model_size_options(self) -> List[Dict[str, str]]:
        """返回模型大小选项。"""
        return [
            {"value": "auto", "label": "自动选择"},
            {"value": "large", "label": "Qwen3-ASR-1.7B"},
            {"value": "small", "label": "Qwen3-ASR-0.6B"},
        ]

    @Property("QVariantList", notify=options_changed)
    def quantization_options(self) -> List[Dict[str, str]]:
        """返回量化模式选项。"""
        return [
            {"value": "auto", "label": "自动"},
            {"value": "fp16", "label": "FP16"},
            {"value": "int8", "label": "INT8"},
            {"value": "int4", "label": "INT4"},
        ]

    @Property("QVariantList", notify=options_changed)
    def device_options(self) -> List[Dict[str, str]]:
        """返回设备选项。"""
        options = [{"value": "auto", "label": "自动"}]
        if self._hardware.has_gpu:
            options.append({"value": "cuda:0", "label": "CUDA 0"})
        options.append({"value": "cpu", "label": "CPU"})
        return options

    @Property("QVariantList", notify=options_changed)
    def breakline_method_options(self) -> List[Dict[str, str]]:
        """返回字幕分行算法选项。"""
        return [
            {"value": "silero_vad", "label": "Silero VAD"},
            {"value": "percentile", "label": "百分位数"},
            {"value": "iqr", "label": "四分位距"},
            {"value": "otsu", "label": "Otsu"},
            {"value": "fixed", "label": "固定阈值"},
            {"value": "clustering", "label": "K-Means"},
        ]

    @Slot(str, object, result=bool)
    def update_setting(self, key: str, value: object) -> bool:
        """更新单个设置项并立即持久化。"""
        if key not in DEFAULT_SETTINGS:
            return False

        normalized = self._normalize_setting(key, value)
        self._settings[key] = normalized
        self._storage.setValue(key, normalized)
        self.settings_changed.emit()
        return True

    @Slot()
    def reset_defaults(self) -> None:
        """恢复默认设置。"""
        self._settings = dict(DEFAULT_SETTINGS)
        for key, value in self._settings.items():
            self._storage.setValue(key, value)
        self.settings_changed.emit()

    def build_model_config(self):
        """构建模型加载配置。"""
        from src.common.asr.model_holder import ModelConfig

        return ModelConfig(
            model_size=self._map_model_size(self._settings["modelSize"]),
            quantization_mode=self._map_quantization_mode(
                self._settings["quantizationMode"]
            ),
            device=self._resolve_device(self._settings["device"]),
        )

    def build_asr_config(self):
        """构建 ASR 推理配置。"""
        from src.common.asr.interface import ASRConfig

        return ASRConfig(
            segment_duration=float(self._settings["segmentDuration"]),
            inference_delay=float(self._settings["inferenceDelay"]),
            low_priority_mode=bool(self._settings["lowPriorityMode"]),
        )

    def build_breakline_config(self):
        """构建字幕分行配置。"""
        from src.common.breakline_algorithm import BreaklineConfig, GapDetectionMethod

        return BreaklineConfig(
            gap_detection_method=GapDetectionMethod(
                str(self._settings["gapDetectionMethod"])
            ),
            max_chars_per_line=int(self._settings["maxCharsPerLine"]),
            max_duration_per_line=float(self._settings["maxDurationPerLine"]),
        )

    def build_system_config(self):
        """构建系统资源限制配置。"""
        from src.common.system_handler import SystemHandlerConfig

        if not bool(self._settings["enableMemoryLimit"]):
            return SystemHandlerConfig(enable_memory_limit=False)

        return SystemHandlerConfig.with_percentage_limits(
            system_memory_percent=float(self._settings["systemMemoryPercent"]),
            gpu_memory_percent=float(self._settings["gpuMemoryPercent"]),
        )

    def _load_settings(self) -> None:
        """从持久化存储加载设置。"""
        for key, default in DEFAULT_SETTINGS.items():
            value_type = type(default)
            loaded = self._storage.value(key, default, type=value_type)
            self._settings[key] = self._normalize_setting(key, loaded)

    def _normalize_setting(self, key: str, value: object) -> Any:
        """归一化单个设置项。"""
        if key == "modelSize":
            text = str(value or "auto").lower()
            return text if text in {"auto", "large", "small"} else "auto"

        if key == "quantizationMode":
            text = str(value or "auto").lower()
            return text if text in {"auto", "fp16", "int8", "int4"} else "auto"

        if key == "device":
            text = str(value or "auto").strip().lower()
            if text in {"auto", "cpu", "cuda:0"}:
                return text
            return "auto"

        if key == "gapDetectionMethod":
            text = str(value or "silero_vad").strip().lower()
            allowed = {item["value"] for item in self.breakline_method_options}
            return text if text in allowed else "silero_vad"

        if key in {"lowPriorityMode", "enableMemoryLimit"}:
            return bool(value)

        if key == "maxCharsPerLine":
            return max(6, min(50, int(value)))

        if key == "segmentDuration":
            return max(5.0, min(60.0, float(value)))

        if key == "inferenceDelay":
            return max(0.0, min(1.0, float(value)))

        if key == "maxDurationPerLine":
            return max(1.0, min(12.0, float(value)))

        if key in {"systemMemoryPercent", "gpuMemoryPercent"}:
            return max(10.0, min(100.0, float(value)))

        return value

    def _map_model_size(self, value: str):
        """将字符串映射为模型大小枚举。"""
        from src.common.asr.model_holder import ModelSize

        mapping = {
            "auto": ModelSize.AUTO,
            "large": ModelSize.LARGE,
            "small": ModelSize.SMALL,
        }
        return mapping.get(value, ModelSize.AUTO)

    def _map_quantization_mode(self, value: str):
        """将字符串映射为量化模式枚举。"""
        from src.common.asr.model_holder import QuantizationMode

        mapping = {
            "auto": QuantizationMode.AUTO,
            "fp16": QuantizationMode.NONE,
            "int8": QuantizationMode.INT8,
            "int4": QuantizationMode.INT4,
        }
        return mapping.get(value, QuantizationMode.AUTO)

    def _resolve_device(self, value: str) -> str:
        """解析最终设备名称。"""
        if value == "auto":
            return "cuda:0" if self._hardware.has_gpu else "cpu"
        return value
