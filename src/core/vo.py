"""
Value Objects Module
统一管理项目中的数据类型定义
"""

from dataclasses import dataclass
from typing import List, Optional


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


@dataclass 
class TranscriptionResult:
    """转录结果"""
    language: str
    text: str
    time_stamps: Optional[List[TimeStampItem]] = None
    duration: float = 0.0
    
    def get_full_text(self) -> str:
        return self.text
    
    def get_formatted_timestamps(self) -> str:
        if not self.time_stamps:
            return ""
        return "\n".join(str(ts) for ts in self.time_stamps)
