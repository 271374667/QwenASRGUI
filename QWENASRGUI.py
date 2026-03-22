"""QwenASR GUI 启动入口。"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from src.application import CompositionRoot
from src.core.paths import PROJECT_DIR


def main() -> int:
    """启动 GUI 应用。"""
    QQuickStyle.setStyle("FluentWinUI3")

    app = QApplication(sys.argv)
    app.setApplicationName("QwenASR")
    app.setOrganizationName("QwenASRGUI")

    root = CompositionRoot()
    root.log_store.install_sink()

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    context.setContextProperty(
        "transcriptionPageViewModel",
        root.transcription_view_model,
    )
    context.setContextProperty(
        "alignmentPageViewModel",
        root.alignment_view_model,
    )
    context.setContextProperty("logPageViewModel", root.log_view_model)
    context.setContextProperty(
        "settingsPageViewModel",
        root.settings_view_model,
    )

    qml_path = Path(PROJECT_DIR) / "qml" / "App.qml"
    engine.load(qml_path.as_uri())

    if not engine.rootObjects():
        root.shutdown()
        return 1

    logger.info("QwenASR GUI 启动完成")
    app.aboutToQuit.connect(root.shutdown)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
