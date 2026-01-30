"""
Breakline Algorithm Module
时间戳聚合与分行算法

提供将字/词级时间戳聚合成句子级时间戳的功能
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import Enum

from loguru import logger


@dataclass
class TimeStampItem:
    """时间戳项"""
    text: str
    start_time: float
    end_time: float
    
    def __str__(self) -> str:
        return f"[{self.start_time:.2f}s - {self.end_time:.2f}s] {self.text}"
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


@dataclass
class AggregatedLine:
    """聚合后的行"""
    text: str
    start_time: float
    end_time: float
    word_count: int
    
    def __str__(self) -> str:
        return f"[{self.start_time:.2f}s - {self.end_time:.2f}s] {self.text}"
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time
    
    def to_srt_time(self, time_seconds: float) -> str:
        """转换为 SRT 时间格式 HH:MM:SS,mmm"""
        hours = int(time_seconds // 3600)
        minutes = int((time_seconds % 3600) // 60)
        seconds = int(time_seconds % 60)
        milliseconds = int((time_seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
    
    def to_srt_entry(self, index: int) -> str:
        """生成 SRT 格式条目"""
        return f"{index}\n{self.to_srt_time(self.start_time)} --> {self.to_srt_time(self.end_time)}\n{self.text}\n"


class GapDetectionMethod(Enum):
    """间隔检测方法"""
    FIXED_THRESHOLD = "fixed"  # 固定阈值
    PERCENTILE = "percentile"  # 百分位数自适应
    CLUSTERING = "clustering"  # K-means 聚类
    IQR = "iqr"  # 四分位距


@dataclass
class BreaklineConfig:
    """分行配置"""
    # 间隔检测
    gap_detection_method: GapDetectionMethod = GapDetectionMethod.PERCENTILE
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


class BreaklineAlgorithm:
    """
    时间戳分行算法
    
    将字/词级时间戳聚合成句子/行级时间戳
    支持多种间隔检测方法和自定义配置
    """
    
    def __init__(self, config: Optional[BreaklineConfig] = None):
        """
        初始化分行算法
        
        Args:
            config: 分行配置，如果为 None 则使用默认配置
        """
        self.config = config or BreaklineConfig()
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
        
        if len(timestamps) == 1:
            return [AggregatedLine(
                text=timestamps[0].text,
                start_time=timestamps[0].start_time,
                end_time=timestamps[0].end_time,
                word_count=1
            )]
        
        # 1. 计算间隔
        gaps = self._calculate_gaps(timestamps)
        
        # 2. 确定间隔阈值
        gap_threshold = self._determine_gap_threshold(gaps)
        logger.debug(f"间隔阈值: {gap_threshold:.3f}秒")
        
        # 3. 根据间隔和长度限制进行分组
        groups = self._group_by_gaps_and_length(timestamps, gaps, gap_threshold)
        
        # 4. 合并短片段（可选）
        if self.config.merge_short_gaps:
            groups = self._merge_short_segments(groups)
        
        # 5. 生成聚合结果
        lines = self._create_aggregated_lines(groups)
        
        logger.info(f"时间戳聚合完成: {len(timestamps)} 个词 → {len(lines)} 行")
        
        return lines
    
    def _calculate_gaps(self, timestamps: List[TimeStampItem]) -> List[float]:
        """计算相邻时间戳之间的间隔"""
        gaps = []
        for i in range(1, len(timestamps)):
            gap = timestamps[i].start_time - timestamps[i-1].end_time
            gaps.append(max(0, gap))  # 防止负值
        return gaps
    
    def _determine_gap_threshold(self, gaps: List[float]) -> float:
        """
        确定间隔阈值
        
        根据配置的方法自动确定分行的间隔阈值
        """
        if not gaps:
            return self.config.fixed_gap_threshold
        
        gaps_array = np.array(gaps)
        
        method = self.config.gap_detection_method
        
        if method == GapDetectionMethod.FIXED_THRESHOLD:
            return self.config.fixed_gap_threshold
        
        elif method == GapDetectionMethod.PERCENTILE:
            # 使用百分位数
            threshold = np.percentile(gaps_array, self.config.percentile_threshold)
            return max(threshold, self.config.min_gap_threshold)
        
        elif method == GapDetectionMethod.IQR:
            # 使用四分位距方法
            q1 = np.percentile(gaps_array, 25)
            q3 = np.percentile(gaps_array, 75)
            iqr = q3 - q1
            threshold = q3 + 1.5 * iqr
            return max(threshold, self.config.min_gap_threshold)
        
        elif method == GapDetectionMethod.CLUSTERING:
            # 使用 K-means 聚类区分短间隔和长间隔
            return self._cluster_gaps(gaps_array)
        
        else:
            return self.config.fixed_gap_threshold
    
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
            threshold = (centers[0] + centers[1]) / 2
            
            return max(threshold, self.config.min_gap_threshold)
            
        except Exception as e:
            logger.warning(f"聚类失败，使用百分位数方法: {e}")
            return max(np.percentile(gaps, 75), self.config.min_gap_threshold)
    
    def _group_by_gaps_and_length(
        self, 
        timestamps: List[TimeStampItem], 
        gaps: List[float], 
        gap_threshold: float
    ) -> List[List[TimeStampItem]]:
        """
        根据间隔和长度限制进行分组
        """
        groups = []
        current_group = [timestamps[0]]
        current_chars = len(timestamps[0].text)
        current_start = timestamps[0].start_time
        
        for i, (ts, gap) in enumerate(zip(timestamps[1:], gaps), 1):
            # 检查是否需要分组
            should_break = False
            
            # 条件1: 间隔超过阈值
            if gap >= gap_threshold:
                should_break = True
            
            # 条件2: 字符数超过限制
            if current_chars + len(ts.text) > self.config.max_chars_per_line:
                should_break = True
            
            # 条件3: 时长超过限制
            if ts.end_time - current_start > self.config.max_duration_per_line:
                should_break = True
            
            if should_break:
                groups.append(current_group)
                current_group = [ts]
                current_chars = len(ts.text)
                current_start = ts.start_time
            else:
                current_group.append(ts)
                current_chars += len(ts.text)
        
        # 添加最后一组
        if current_group:
            groups.append(current_group)
        
        return groups
    
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
    
    def _format_vtt_time(self, seconds: float) -> str:
        """格式化为 VTT 时间格式 HH:MM:SS.mmm"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
    
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
        
        durations = [line.duration for line in lines]
        char_counts = [len(line.text) for line in lines]
        
        return {
            "total_lines": len(lines),
            "total_duration": sum(durations),
            "total_chars": sum(char_counts),
            "avg_duration": np.mean(durations),
            "avg_chars": np.mean(char_counts),
            "max_duration": max(durations),
            "max_chars": max(char_counts),
            "min_duration": min(durations),
            "min_chars": min(char_counts),
        }
