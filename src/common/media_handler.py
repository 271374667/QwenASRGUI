"""
Media Handler Module
提供音频文件加载与处理功能
"""

import librosa
import numpy as np
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Union

from loguru import logger


@dataclass
class AudioData:
    """音频数据容器"""
    data: np.ndarray  # 音频波形数据
    sample_rate: int  # 采样率
    path: Optional[str] = None  # 源文件路径
    
    @property
    def duration(self) -> float:
        """音频时长（秒）"""
        return len(self.data) / self.sample_rate
    
    @property
    def num_samples(self) -> int:
        """样本数"""
        return len(self.data)
    
    def to_tuple(self) -> Tuple[np.ndarray, int]:
        """转换为 (data, sample_rate) 元组"""
        return (self.data, self.sample_rate)
    
    def __repr__(self) -> str:
        return f"AudioData(duration={self.duration:.2f}s, sr={self.sample_rate}, samples={self.num_samples})"


class MediaHandler:
    """
    媒体文件处理器
    
    提供音频文件加载、重采样、分段等功能，支持缓存避免重复加载。
    
    用法概览：
    - 加载音频：`load()` 加载音频文件
    - 分段：`segment()` 将音频分段
    - 缓存管理：`clear_cache()` 清除缓存
    
    公开方法：
    - load(path, sample_rate=16000): 加载音频文件
    - load_from_array(data, sample_rate): 从 numpy 数组创建 AudioData
    - segment(audio, segment_duration): 将音频分段
    - resample(audio, target_sr): 重采样音频
    - clear_cache(): 清除已加载的音频缓存
    
    典型示例：
        handler = MediaHandler()
        audio = handler.load("audio.mp3")
        print(f"时长: {audio.duration}秒")
        
        segments = handler.segment(audio, segment_duration=15.0)
        print(f"分段数: {len(segments)}")
    """
    
    def __init__(self, default_sample_rate: int = 16000):
        """
        初始化媒体处理器
        
        Args:
            default_sample_rate: 默认采样率
        """
        self.default_sample_rate = default_sample_rate
        self._cache: dict[str, AudioData] = {}
        logger.debug(f"MediaHandler 初始化: 默认采样率={default_sample_rate}Hz")
    
    def load(
        self,
        path: Union[str, Path],
        sample_rate: Optional[int] = None,
        use_cache: bool = True
    ) -> AudioData:
        """
        加载音频文件
        
        Args:
            path: 音频文件路径
            sample_rate: 目标采样率，None 则使用默认采样率
            use_cache: 是否使用缓存
            
        Returns:
            AudioData 对象
        """
        path_str = str(path)
        sr = sample_rate or self.default_sample_rate
        cache_key = f"{path_str}:{sr}"
        
        # 检查缓存
        if use_cache and cache_key in self._cache:
            logger.debug(f"从缓存加载音频: {path_str}")
            return self._cache[cache_key]
        
        # 加载音频
        logger.info(f"加载音频: {path_str}")
        try:
            data, loaded_sr = librosa.load(path_str, sr=sr)
            audio = AudioData(data=data, sample_rate=int(loaded_sr), path=path_str)
            logger.info(f"音频加载完成: {audio}")
            
            # 缓存
            if use_cache:
                self._cache[cache_key] = audio
            
            return audio
            
        except Exception as e:
            logger.error(f"音频加载失败: {path_str}, 错误: {e}")
            raise
    
    def load_from_array(
        self,
        data: np.ndarray,
        sample_rate: int,
        path: Optional[str] = None
    ) -> AudioData:
        """
        从 numpy 数组创建 AudioData
        
        Args:
            data: 音频波形数据
            sample_rate: 采样率
            path: 可选的源文件路径标识
            
        Returns:
            AudioData 对象
        """
        return AudioData(data=data, sample_rate=sample_rate, path=path)
    
    def segment(
        self,
        audio: AudioData,
        segment_duration: float = 15.0
    ) -> List[AudioData]:
        """
        将音频分段
        
        Args:
            audio: 音频数据
            segment_duration: 每段时长（秒）
            
        Returns:
            分段后的 AudioData 列表
        """
        segment_samples = int(segment_duration * audio.sample_rate)
        segments = []
        
        for start in range(0, audio.num_samples, segment_samples):
            end = min(start + audio.num_samples, audio.num_samples)
            segment_data = audio.data[start:end]
            segments.append(AudioData(
                data=segment_data,
                sample_rate=audio.sample_rate,
                path=audio.path
            ))
        
        logger.debug(f"音频分段完成: {len(segments)} 段 (每段 {segment_duration}秒)")
        return segments
    
    def segment_with_tuples(
        self,
        audio: AudioData,
        segment_duration: float = 15.0
    ) -> List[Tuple[np.ndarray, int]]:
        """
        将音频分段并返回 (data, sample_rate) 元组列表
        
        用于兼容需要元组格式的 API
        
        Args:
            audio: 音频数据
            segment_duration: 每段时长（秒）
            
        Returns:
            分段后的 (data, sample_rate) 元组列表
        """
        segment_samples = int(segment_duration * audio.sample_rate)
        segments = []
        
        for start in range(0, audio.num_samples, segment_samples):
            end = min(start + segment_samples, audio.num_samples)
            segment_data = audio.data[start:end]
            segments.append((segment_data, audio.sample_rate))
        
        logger.debug(f"音频分段完成: {len(segments)} 段 (每段 {segment_duration}秒)")
        return segments
    
    def resample(
        self,
        audio: AudioData,
        target_sr: int
    ) -> AudioData:
        """
        重采样音频
        
        Args:
            audio: 音频数据
            target_sr: 目标采样率
            
        Returns:
            重采样后的 AudioData
        """
        if audio.sample_rate == target_sr:
            return audio
        
        logger.debug(f"重采样: {audio.sample_rate}Hz -> {target_sr}Hz")
        resampled = librosa.resample(
            audio.data,
            orig_sr=audio.sample_rate,
            target_sr=target_sr
        )
        
        return AudioData(
            data=resampled,
            sample_rate=target_sr,
            path=audio.path
        )
    
    def clear_cache(self) -> None:
        """清除音频缓存"""
        count = len(self._cache)
        self._cache.clear()
        logger.debug(f"已清除 {count} 个缓存条目")
    
    def get_cache_info(self) -> dict:
        """获取缓存信息"""
        return {
            "count": len(self._cache),
            "keys": list(self._cache.keys())
        }
