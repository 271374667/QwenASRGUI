"""文本导出用例。"""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from src.application.file_support import normalize_local_path


class ExportTextUseCase:
    """负责将文本内容导出到本地文件。"""

    def execute(self, file_path: str, content: str, success_message: str) -> bool:
        """执行导出。"""
        normalized = normalize_local_path(file_path)
        if not normalized or not content:
            return False

        output = Path(normalized)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        logger.success(success_message.format(path=output))
        return True
