"""
Breakline Algorithm Module
时间戳聚合与分行算法

提供将字/词级时间戳聚合成句子级时间戳的功能

性能优化版本：使用 NumPy 向量化操作
支持 Silero VAD 进行语音活动检测
"""

import numpy as np
import torch
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Any
from enum import Enum

from loguru import logger

from src.core.vo import TimeStampItem, AggregatedLine


class GapDetectionMethod(Enum):
    """
    间隔检测方法
    
    性能排序（快→慢）: FIXED > PERCENTILE ≈ IQR > OTSU > SILERO_VAD > CLUSTERING
    准确性排序（高→低）: SILERO_VAD ≈ CLUSTERING ≈ OTSU > IQR ≈ PERCENTILE > FIXED
    """
    FIXED_THRESHOLD = "fixed"  # 固定阈值 - O(1)，最快但需手动调参
    PERCENTILE = "percentile"  # 百分位数自适应 - O(n log n)，推荐
    IQR = "iqr"  # 四分位距 - O(n log n)，对离群值鲁棒
    OTSU = "otsu"  # 大津算法 - O(n × bins)，图像处理经典方法，快速二分类
    SILERO_VAD = "silero_vad"  # Silero VAD - 基于深度学习的语音活动检测，高精度
    CLUSTERING = "clustering"  # K-means 聚类 - O(n × k × iter)，最准但最慢


@dataclass
class VADConfig:
    """VAD 配置"""
    # 检测参数
    threshold: float = 0.5  # 语音活动阈值 (0-1)
    min_speech_duration_ms: int = 250  # 最小语音片段时长（毫秒）
    min_silence_duration_ms: int = 100  # 最小静音片段时长（毫秒）
    speech_pad_ms: int = 30  # 语音片段前后填充（毫秒）
    
    # 采样率
    sample_rate: int = 16000  # 采样率（Silero VAD 支持 8000 或 16000）


@dataclass
class BreaklineConfig:
    """分行配置"""
    # 间隔检测
    gap_detection_method: GapDetectionMethod = GapDetectionMethod.SILERO_VAD
    fixed_gap_threshold: float = 0.5  # 固定阈值方法的间隔阈值（秒）
    percentile_threshold: float = 75  # 百分位数方法的阈值
    min_gap_threshold: float = 0.3  # 最小间隔阈值（秒）
    
    # 长度限制
    max_chars_per_line: int = 40  # 每行最大字符数
    max_duration_per_line: float = 8.0  # 每行最大时长（秒）
    min_chars_per_line: int = 2  # 每行最小字符数（避免碎片）
    
    # 合并选项
    merge_short_gaps: bool = True  # 是否合并短间隔
    merge_threshold: float = 0.1  # 合并阈值（秒）
    
    # VAD 配置（当使用 SILERO_VAD 方法时）
    vad_config: VADConfig = field(default_factory=VADConfig)


@dataclass
class SpeechSegment:
    """语音片段"""
    start_time: float  # 开始时间（秒）
    end_time: float    # 结束时间（秒）
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


class SileroVAD:
    """
    Silero VAD 语音活动检测器
    
    基于 silero-vad pip 包的语音活动检测，用于识别音频中的语音和静音片段。
    使用 ONNX 推理，无需 GPU，模型已包含在 pip 包中，无需额外下载。
    
    用法概览：
    - 创建实例：可传入 VADConfig 指定检测参数
    - 检测：`detect()` 检测音频中的语音片段
    - 分割：`get_silence_segments()` 获取静音片段（用于分行）
    
    公开方法：
    - detect(audio, sample_rate): 检测语音片段
    - get_silence_segments(audio, sample_rate): 获取静音片段
    - reset_states(): 重置模型内部状态
    
    典型示例：
        vad = SileroVAD()
        speech_segments = vad.detect(audio_array, 16000)
        for seg in speech_segments:
            print(f"{seg.start_time:.2f}s - {seg.end_time:.2f}s")
    """
    
    _model: Optional[Any] = None  # 类级别缓存模型
    
    def __init__(self, config: Optional[VADConfig] = None):
        """
        初始化 Silero VAD
        
        Args:
            config: VAD 配置，如果为 None 则使用默认配置
        """
        self.config = config or VADConfig()
        self._ensure_model_loaded()
        logger.debug(f"Silero VAD 初始化: 阈值={self.config.threshold}")
    
    def _ensure_model_loaded(self) -> None:
        """确保模型已加载（使用类级别缓存）"""
        if SileroVAD._model is None:
            logger.info("加载 Silero VAD 模型...")
            try:
                from silero_vad import load_silero_vad
                SileroVAD._model = load_silero_vad()
                logger.success("Silero VAD 模型加载完成")
            except ImportError:
                logger.error("silero-vad 未安装，请运行: uv add silero-vad")
                raise ImportError("请安装 silero-vad: uv add silero-vad")
            except Exception as e:
                logger.error(f"Silero VAD 模型加载失败: {e}")
                raise
    
    def detect(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000
    ) -> List[SpeechSegment]:
        """
        检测音频中的语音片段
        
        Args:
            audio: 音频数据（numpy 数组，单声道）
            sample_rate: 采样率（支持 8000 或 16000）
            
        Returns:
            语音片段列表
        """
        if len(audio) == 0:
            return []
        
        # 确保采样率正确
        if sample_rate not in (8000, 16000):
            logger.warning(f"不支持的采样率 {sample_rate}，Silero VAD 仅支持 8000 或 16000")
            return []
        
        try:
            from silero_vad import get_speech_timestamps
            
            # 转换为 torch tensor
            audio_tensor = torch.from_numpy(audio).float()
            
            # 使用 silero-vad 的官方 API
            speech_timestamps = get_speech_timestamps(
                audio_tensor,
                SileroVAD._model,
                threshold=self.config.threshold,
                sampling_rate=sample_rate,
                min_speech_duration_ms=self.config.min_speech_duration_ms,
                min_silence_duration_ms=self.config.min_silence_duration_ms,
                speech_pad_ms=self.config.speech_pad_ms,
            )
            
            # 转换为 SpeechSegment 列表
            segments = []
            for ts in speech_timestamps:
                start_sec = ts['start'] / sample_rate
                end_sec = ts['end'] / sample_rate
                segments.append(SpeechSegment(start_time=start_sec, end_time=end_sec))
            
            logger.debug(f"检测到 {len(segments)} 个语音片段")
            return segments
            
        except Exception as e:
            logger.error(f"VAD 检测失败: {e}")
            return []
    
    def get_silence_segments(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        total_duration: Optional[float] = None
    ) -> List[Tuple[float, float]]:
        """
        获取静音片段
        
        Args:
            audio: 音频数据
            sample_rate: 采样率
            total_duration: 总时长（秒），如果为 None 则从音频计算
            
        Returns:
            静音片段列表，每个元素为 (start_time, end_time)
        """
        if total_duration is None:
            total_duration = len(audio) / sample_rate
        
        speech_segments = self.detect(audio, sample_rate)
        
        if not speech_segments:
            return [(0.0, total_duration)]
        
        silence_segments = []
        
        # 开头的静音
        if speech_segments[0].start_time > 0:
            silence_segments.append((0.0, speech_segments[0].start_time))
        
        # 语音片段之间的静音
        for i in range(len(speech_segments) - 1):
            current_end = speech_segments[i].end_time
            next_start = speech_segments[i + 1].start_time
            if next_start > current_end:
                silence_segments.append((current_end, next_start))
        
        # 结尾的静音
        if speech_segments[-1].end_time < total_duration:
            silence_segments.append((speech_segments[-1].end_time, total_duration))
        
        return silence_segments
    
    def reset_states(self) -> None:
        """重置模型内部状态"""
        if SileroVAD._model is not None:
            SileroVAD._model.reset_states()
    
    @classmethod
    def unload_model(cls) -> None:
        """卸载模型释放内存"""
        if cls._model is not None:
            del cls._model
            cls._model = None
            logger.info("Silero VAD 模型已卸载")


class BreaklineAlgorithm:
    """
    时间戳分行算法

    将字/词级时间戳聚合成句子/行级时间戳，支持多种间隔检测方法与自定义配置。

    用法概览：
    - 创建实例：可传入 BreaklineConfig 指定分行策略与限制
    - 聚合：`aggregate()` 将词级时间戳聚合为行级
    - VAD 聚合：`aggregate_with_audio()` 使用音频进行 VAD 检测后聚合
    - 导出：`to_srt()` / `to_vtt()` 生成字幕文本
    - 统计：`get_statistics()` 获取聚合结果统计
    - 性能对比：`benchmark_methods()` 对比不同间隔检测方法

    公开方法：
    - aggregate(timestamps): 聚合时间戳为行级结构
    - aggregate_with_audio(timestamps, audio, sample_rate): 使用 VAD 检测聚合
    - to_srt(lines): 输出 SRT 字幕字符串
    - to_vtt(lines): 输出 WebVTT 字幕字符串
    - get_statistics(lines): 返回聚合统计信息
    - benchmark_methods(timestamps, n_runs=10): 不同方法性能对比
    """
    
    def __init__(self, config: Optional[BreaklineConfig] = None):
        """
        初始化分行算法
        
        Args:
            config: 分行配置，如果为 None 则使用默认配置
        """
        self.config = config or BreaklineConfig()
        self._audio: Optional[np.ndarray] = None  # 音频数据（用于 VAD）
        self._sample_rate: int = 16000  # 采样率
        self._vad: Optional[SileroVAD] = None  # VAD 实例（延迟初始化）
        logger.debug(f"分行算法初始化: 方法={self.config.gap_detection_method.value}, "
                    f"最大字符数={self.config.max_chars_per_line}")
    
    def aggregate(self, timestamps: List[TimeStampItem]) -> List[AggregatedLine]:
        """
        聚合时间戳
        
        Args:
            timestamps: 字/词级时间戳列表
            
        Returns:
            聚合后的行列表
        """
        if not timestamps:
            return []
        
        n = len(timestamps)
        if n == 1:
            return [AggregatedLine(
                text=timestamps[0].text,
                start_time=timestamps[0].start_time,
                end_time=timestamps[0].end_time,
                word_count=1
            )]
        
        # 1. 向量化提取时间和文本信息
        start_times, end_times, texts, char_lens = self._vectorize_timestamps(timestamps)
        
        # 2. 向量化计算间隔
        gaps = self._calculate_gaps_vectorized(start_times, end_times)
        
        # 3. 确定间隔阈值
        gap_threshold = self._determine_gap_threshold(gaps)
        logger.debug(f"间隔阈值: {gap_threshold:.3f}秒")
        
        # 4. 向量化找出分割点
        break_indices = self._find_break_indices_vectorized(
            gaps, start_times, end_times, char_lens, gap_threshold
        )
        
        # 5. 根据分割点创建分组
        groups = self._create_groups_from_indices(timestamps, break_indices)
        
        # 6. 合并短片段（可选）
        if self.config.merge_short_gaps:
            groups = self._merge_short_segments(groups)
        
        # 7. 生成聚合结果
        lines = self._create_aggregated_lines(groups)
        
        logger.info(f"时间戳聚合完成: {n} 个词 → {len(lines)} 行")
        
        return lines
    
    def aggregate_with_audio(
        self,
        timestamps: List[TimeStampItem],
        audio: np.ndarray,
        sample_rate: int = 16000
    ) -> List[AggregatedLine]:
        """
        使用音频 VAD 检测进行聚合
        
        结合 Silero VAD 检测静音片段，更准确地确定分行位置。
        
        Args:
            timestamps: 字/词级时间戳列表
            audio: 音频数据（numpy 数组，单声道）
            sample_rate: 采样率
            
        Returns:
            聚合后的行列表
        """
        if not timestamps:
            return []
        
        # 保存音频信息供 VAD 使用
        self._audio = audio
        self._sample_rate = sample_rate
        
        # 初始化 VAD（延迟加载）
        if self._vad is None:
            self._vad = SileroVAD(self.config.vad_config)
        
        # 使用原有的聚合逻辑，但在 _determine_gap_threshold 中使用 VAD
        original_method = self.config.gap_detection_method
        self.config.gap_detection_method = GapDetectionMethod.SILERO_VAD
        
        try:
            lines = self.aggregate(timestamps)
        finally:
            # 恢复原始方法
            self.config.gap_detection_method = original_method
            # 清理音频数据
            self._audio = None
        
        return lines
    
    def detect_speech_segments(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000
    ) -> List[SpeechSegment]:
        """
        检测音频中的语音片段
        
        Args:
            audio: 音频数据
            sample_rate: 采样率
            
        Returns:
            语音片段列表
        """
        if self._vad is None:
            self._vad = SileroVAD(self.config.vad_config)
        return self._vad.detect(audio, sample_rate)

    def to_srt(self, lines: List[AggregatedLine]) -> str:
        """
        将聚合行转换为 SRT 格式字幕
        
        Args:
            lines: 聚合行列表
            
        Returns:
            SRT 格式字符串
        """
        srt_entries = []
        for i, line in enumerate(lines, 1):
            srt_entries.append(line.to_srt_entry(i))
        return "\n".join(srt_entries)
    
    def to_vtt(self, lines: List[AggregatedLine]) -> str:
        """
        将聚合行转换为 WebVTT 格式字幕
        
        Args:
            lines: 聚合行列表
            
        Returns:
            WebVTT 格式字符串
        """
        vtt_lines = ["WEBVTT", ""]
        
        for line in lines:
            start = self._format_vtt_time(line.start_time)
            end = self._format_vtt_time(line.end_time)
            vtt_lines.append(f"{start} --> {end}")
            vtt_lines.append(line.text)
            vtt_lines.append("")
        
        return "\n".join(vtt_lines)
    
    def get_statistics(self, lines: List[AggregatedLine]) -> dict:
        """
        获取聚合统计信息
        
        Args:
            lines: 聚合行列表
            
        Returns:
            统计信息字典
        """
        if not lines:
            return {}
        
        durations = np.array([line.duration for line in lines])
        char_counts = np.array([len(line.text) for line in lines])
        
        return {
            "total_lines": len(lines),
            "total_duration": float(np.sum(durations)),
            "total_chars": int(np.sum(char_counts)),
            "avg_duration": float(np.mean(durations)),
            "avg_chars": float(np.mean(char_counts)),
            "max_duration": float(np.max(durations)),
            "max_chars": int(np.max(char_counts)),
            "min_duration": float(np.min(durations)),
            "min_chars": int(np.min(char_counts)),
        }
    
    @staticmethod
    def benchmark_methods(
        timestamps: List[TimeStampItem],
        n_runs: int = 10
    ) -> dict:
        """
        对比不同间隔检测方法的性能
        
        Args:
            timestamps: 时间戳列表
            n_runs: 每个方法运行次数
            
        Returns:
            各方法的平均耗时和结果行数
        """
        import time
        
        results = {}
        
        for method in GapDetectionMethod:
            config = BreaklineConfig(gap_detection_method=method)
            algo = BreaklineAlgorithm(config)
            
            times = []
            line_count = 0
            
            for _ in range(n_runs):
                start = time.perf_counter()
                lines = algo.aggregate(timestamps)
                elapsed = time.perf_counter() - start
                times.append(elapsed)
                line_count = len(lines)
            
            avg_time = np.mean(times) * 1000  # 转换为毫秒
            
            results[method.value] = {
                "avg_time_ms": round(avg_time, 3),
                "line_count": line_count,
            }
            
            logger.info(f"{method.value}: 平均耗时 {avg_time:.3f}ms, 生成 {line_count} 行")
        
        return results

    def _vectorize_timestamps(
        self, timestamps: List[TimeStampItem]
    ) -> Tuple[np.ndarray, np.ndarray, List[str], np.ndarray]:
        """向量化提取时间戳信息"""
        n = len(timestamps)
        start_times = np.empty(n, dtype=np.float64)
        end_times = np.empty(n, dtype=np.float64)
        texts = []
        char_lens = np.empty(n, dtype=np.int32)

        for i, ts in enumerate(timestamps):
            start_times[i] = ts.start_time
            end_times[i] = ts.end_time
            texts.append(ts.text)
            char_lens[i] = len(ts.text)

        return start_times, end_times, texts, char_lens

    def _calculate_gaps_vectorized(
        self, start_times: np.ndarray, end_times: np.ndarray
    ) -> np.ndarray:
        """向量化计算间隔"""
        gaps = start_times[1:] - end_times[:-1]
        return np.maximum(gaps, 0)  # 防止负值

    def _find_break_indices_vectorized(
        self,
        gaps: np.ndarray,
        start_times: np.ndarray,
        end_times: np.ndarray,
        char_lens: np.ndarray,
        gap_threshold: float
    ) -> np.ndarray:
        """
        向量化找出分割点索引

        返回需要在其前面分割的索引数组
        """
        n = len(start_times)

        # 条件1: 间隔超过阈值
        gap_breaks = gaps >= gap_threshold

        # 条件2: 累积字符数超过限制（需要迭代计算）
        # 条件3: 时长超过限制
        # 这两个条件依赖于分组状态，使用优化的迭代方法

        break_mask = np.zeros(n - 1, dtype=bool)
        break_mask |= gap_breaks

        # 使用滑动窗口检测长度超限
        cumsum_chars = np.cumsum(char_lens)

        # 找出所有潜在的分割点，然后验证长度和时长约束
        current_start_idx = 0
        current_char_sum = char_lens[0]

        for i in range(1, n):
            potential_char_sum = cumsum_chars[i] - (cumsum_chars[current_start_idx - 1] if current_start_idx > 0 else 0)
            potential_duration = end_times[i] - start_times[current_start_idx]

            should_break = (
                break_mask[i - 1] or  # 已经标记为分割点
                potential_char_sum > self.config.max_chars_per_line or
                potential_duration > self.config.max_duration_per_line
            )

            if should_break:
                break_mask[i - 1] = True
                current_start_idx = i
                current_char_sum = char_lens[i]
            else:
                current_char_sum += char_lens[i]

        return np.where(break_mask)[0] + 1  # +1 因为 break_mask 对应的是 gap 索引

    def _create_groups_from_indices(
        self, timestamps: List[TimeStampItem], break_indices: np.ndarray
    ) -> List[List[TimeStampItem]]:
        """根据分割索引创建分组"""
        groups = []
        prev_idx = 0

        for idx in break_indices:
            groups.append(timestamps[prev_idx:idx])
            prev_idx = idx

        # 添加最后一组
        if prev_idx < len(timestamps):
            groups.append(timestamps[prev_idx:])

        return groups

    def _calculate_gaps(self, timestamps: List[TimeStampItem]) -> np.ndarray:
        """计算相邻时间戳之间的间隔（向量化版本）"""
        if len(timestamps) < 2:
            return np.array([])

        start_times = np.array([ts.start_time for ts in timestamps])
        end_times = np.array([ts.end_time for ts in timestamps])

        gaps = start_times[1:] - end_times[:-1]
        return np.maximum(gaps, 0)

    def _determine_gap_threshold(self, gaps: np.ndarray) -> float:
        """
        确定间隔阈值

        根据配置的方法自动确定分行的间隔阈值
        """
        if len(gaps) == 0:
            return self.config.fixed_gap_threshold

        method = self.config.gap_detection_method

        if method == GapDetectionMethod.FIXED_THRESHOLD:
            logger.info(f"使用分割算法: 固定阈值 (阈值={self.config.fixed_gap_threshold}秒)")
            return self.config.fixed_gap_threshold

        elif method == GapDetectionMethod.PERCENTILE:
            # 使用百分位数 - O(n log n)
            logger.info(f"使用分割算法: 百分位数自适应 (百分位={self.config.percentile_threshold})")
            threshold = float(np.percentile(gaps, self.config.percentile_threshold))
            return max(threshold, self.config.min_gap_threshold)

        elif method == GapDetectionMethod.IQR:
            # 使用四分位距方法 - O(n log n)
            logger.info("使用分割算法: 四分位距 (IQR)")
            q1, q3 = np.percentile(gaps, [25, 75])
            iqr = float(q3 - q1)
            threshold = float(q3) + 1.5 * iqr
            return max(threshold, self.config.min_gap_threshold)

        elif method == GapDetectionMethod.OTSU:
            # 使用大津算法 - O(n × bins)，比 K-means 快很多
            logger.info("使用分割算法: 大津算法 (Otsu)")
            return self._otsu_threshold(gaps)

        elif method == GapDetectionMethod.SILERO_VAD:
            # 使用 Silero VAD 检测静音区域
            logger.info("使用分割算法: Silero VAD")
            return self._silero_vad_threshold(gaps)

        elif method == GapDetectionMethod.CLUSTERING:
            # 使用 K-means 聚类区分短间隔和长间隔
            logger.info("使用分割算法: K-means 聚类")
            return self._cluster_gaps(gaps)

        else:
            logger.info(f"使用分割算法: 固定阈值 (默认, 阈值={self.config.fixed_gap_threshold}秒)")
            return self.config.fixed_gap_threshold

    def _otsu_threshold(self, gaps: np.ndarray) -> float:
        """
        大津算法（Otsu's method）确定阈值

        经典的图像二值化算法，用于找到最佳分割阈值
        比 K-means 快约 10-50 倍，准确性相近

        时间复杂度: O(n + bins)
        """
        # 过滤掉极小值
        valid_gaps = gaps[gaps > 0.01]

        if len(valid_gaps) < 2:
            return self.config.min_gap_threshold

        # 创建直方图
        n_bins = min(256, len(valid_gaps))
        hist, bin_edges = np.histogram(valid_gaps, bins=n_bins)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

        # 归一化直方图
        hist = hist.astype(np.float64)
        hist_norm = hist / hist.sum()

        # 计算累积和与累积均值
        cumsum = np.cumsum(hist_norm)
        cumsum_mean = np.cumsum(hist_norm * bin_centers)

        # 全局均值
        global_mean = cumsum_mean[-1]

        # 计算类间方差
        # 避免除以零
        with np.errstate(divide='ignore', invalid='ignore'):
            between_class_variance = (
                (global_mean * cumsum - cumsum_mean) ** 2 /
                (cumsum * (1 - cumsum))
            )

        # 替换 nan/inf 为 0
        between_class_variance = np.nan_to_num(between_class_variance, nan=0, posinf=0, neginf=0)

        # 找到最大类间方差对应的阈值
        optimal_idx = np.argmax(between_class_variance)
        threshold = float(bin_centers[optimal_idx])

        return max(threshold, self.config.min_gap_threshold)

    def _cluster_gaps(self, gaps: np.ndarray) -> float:
        """
        使用 K-means 聚类确定间隔阈值

        将间隔分为"短间隔"和"长间隔"两类
        """
        from sklearn.cluster import KMeans

        # 过滤掉零值
        non_zero_gaps = gaps[gaps > 0.01]

        if len(non_zero_gaps) < 2:
            return self.config.min_gap_threshold

        # 重塑为二维数组
        X = non_zero_gaps.reshape(-1, 1)

        try:
            kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
            kmeans.fit(X)

            # 获取两个聚类中心
            centers = sorted(kmeans.cluster_centers_.flatten())

            # 阈值取两个中心的中点
            threshold = float((centers[0] + centers[1]) / 2)

            return max(threshold, self.config.min_gap_threshold)

        except Exception as e:
            logger.warning(f"聚类失败，使用百分位数方法: {e}")
            return max(float(np.percentile(gaps, 75)), self.config.min_gap_threshold)

    def _silero_vad_threshold(self, gaps: np.ndarray) -> float:
        """
        使用 Silero VAD 检测结果确定间隔阈值
        
        分析时间戳间隔与 VAD 检测到的静音区域的对应关系，
        将落在静音区域内的间隔识别为分割点。
        
        如果没有音频数据可用，则回退到百分位数方法。
        
        Returns:
            间隔阈值（秒）
        """
        # 如果没有音频数据，回退到百分位数方法
        if self._audio is None:
            logger.warning("VAD 方法需要音频数据，回退到百分位数方法")
            threshold = float(np.percentile(gaps, self.config.percentile_threshold))
            return max(threshold, self.config.min_gap_threshold)
        
        try:
            # 初始化 VAD
            if self._vad is None:
                self._vad = SileroVAD(self.config.vad_config)
            
            # 检测静音片段
            silence_segments = self._vad.get_silence_segments(
                self._audio,
                self._sample_rate,
                total_duration=len(self._audio) / self._sample_rate
            )
            
            if not silence_segments:
                logger.debug("未检测到静音片段，使用百分位数方法")
                threshold = float(np.percentile(gaps, self.config.percentile_threshold))
                return max(threshold, self.config.min_gap_threshold)
            
            # 计算静音片段的时长分布
            silence_durations = np.array([end - start for start, end in silence_segments])
            
            # 使用静音时长的中位数作为阈值参考
            median_silence = float(np.median(silence_durations))
            
            # 结合间隔数据，取较小值确保不会遗漏分割点
            gap_threshold = float(np.percentile(gaps, 50))  # 使用中位数
            
            # 最终阈值：取静音中位数和间隔中位数的较小值
            threshold = min(median_silence, gap_threshold)
            
            logger.debug(f"VAD 静音中位数: {median_silence:.3f}s, "
                        f"间隔中位数: {gap_threshold:.3f}s, "
                        f"最终阈值: {threshold:.3f}s")
            
            return max(threshold, self.config.min_gap_threshold)
            
        except Exception as e:
            logger.warning(f"VAD 检测失败，回退到百分位数方法: {e}")
            threshold = float(np.percentile(gaps, self.config.percentile_threshold))
            return max(threshold, self.config.min_gap_threshold)

    def _merge_short_segments(
        self,
        groups: List[List[TimeStampItem]]
    ) -> List[List[TimeStampItem]]:
        """
        合并过短的片段
        """
        if len(groups) <= 1:
            return groups

        merged = []
        i = 0

        while i < len(groups):
            current = groups[i]
            current_chars = sum(len(ts.text) for ts in current)

            # 如果当前组太短，尝试与下一组合并
            if current_chars < self.config.min_chars_per_line and i + 1 < len(groups):
                next_group = groups[i + 1]
                next_chars = sum(len(ts.text) for ts in next_group)

                # 检查合并后是否超过限制
                if current_chars + next_chars <= self.config.max_chars_per_line:
                    merged.append(current + next_group)
                    i += 2
                    continue

            merged.append(current)
            i += 1

        return merged

    def _create_aggregated_lines(
        self,
        groups: List[List[TimeStampItem]]
    ) -> List[AggregatedLine]:
        """
        从分组创建聚合行
        """
        lines = []

        for group in groups:
            if not group:
                continue

            text = "".join(ts.text for ts in group)
            start_time = group[0].start_time
            end_time = group[-1].end_time

            lines.append(AggregatedLine(
                text=text,
                start_time=start_time,
                end_time=end_time,
                word_count=len(group)
            ))

        return lines

    def _format_vtt_time(self, seconds: float) -> str:
        """格式化为 VTT 时间格式 HH:MM:SS.mmm"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
