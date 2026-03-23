"""页面本地状态模型。"""

from dataclasses import dataclass


@dataclass
class TranscriptionPageState:
    selectedFilePath: str = ""
    selectedFileName: str = "未选择媒体文件"
    fileSuffix: str = "--"
    fileSizeText: str = "--"
    isTranscribing: bool = False
    language: str = "--"
    durationText: str = "--"
    subtitleLineCount: int = 0
    timestampCount: int = 0
    transcriptText: str = ""
    subtitleText: str = ""
    lastError: str = ""
    taskStatusText: str = "请选择媒体文件开始转录"
    hasResult: bool = False


@dataclass
class AlignmentPageState:
    selectedFilePath: str = ""
    selectedFileName: str = "未选择音频文件"
    fileSuffix: str = "--"
    fileSizeText: str = "--"
    inputText: str = ""
    selectedLanguage: str = "Chinese"
    isAligning: bool = False
    taskStatusText: str = "请选择音频并输入待对齐文本"
    audioDurationText: str = "--"
    wordCount: int = 0
    lineCount: int = 0
    subtitleText: str = ""
    rawTimestampText: str = ""
    lastError: str = ""
    hasResult: bool = False
