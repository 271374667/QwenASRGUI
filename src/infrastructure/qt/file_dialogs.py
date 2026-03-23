"""Qt 文件对话框基础设施。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog

from src.application.file_support import (
    LOG_FILE_FILTER,
    MEDIA_FILE_FILTER,
    SRT_FILE_FILTER,
    TEXT_FILE_FILTER,
)


class QtFileDialogGateway:
    """封装 Qt 文件打开和保存对话框。"""

    def pick_media_file(self, title: str) -> str:
        """选择媒体文件。"""
        file_path, _ = QFileDialog.getOpenFileName(None, title, "", MEDIA_FILE_FILTER)
        return file_path

    def save_transcript(self, default_path: str) -> str:
        """选择转录文本导出路径。"""
        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "导出转录文本",
            default_path,
            TEXT_FILE_FILTER,
        )
        return file_path

    def save_subtitle(self, title: str, default_path: str) -> str:
        """选择字幕导出路径。"""
        file_path, _ = QFileDialog.getSaveFileName(
            None,
            title,
            default_path,
            SRT_FILE_FILTER,
        )
        return file_path

    def save_logs(self, default_path: str | None = None) -> str:
        """选择日志导出路径。"""
        initial_path = default_path or str(Path.cwd() / "qwenasr.log")
        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "导出日志",
            initial_path,
            LOG_FILE_FILTER,
        )
        return file_path
