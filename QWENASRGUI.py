"""QwenASR GUI 启动入口。"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from src.core.paths import PROJECT_DIR


def main() -> int:
    """启动 GUI 应用。"""
    from src.service import (
        AlignmentService,
        ApplicationService,
        LogService,
        SettingsService,
        TranscriptionService,
    )

    QQuickStyle.setStyle("FluentWinUI3")

    app = QApplication(sys.argv)
    app.setApplicationName("QwenASR")
    app.setOrganizationName("QwenASRGUI")

    log_service = LogService()
    log_service.install_sink()

    application_service = ApplicationService()
    settings_service = SettingsService()
    transcription_service = TranscriptionService(application_service, settings_service)
    alignment_service = AlignmentService(application_service, settings_service)

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    context.setContextProperty("applicationService", application_service)
    context.setContextProperty("settingsService", settings_service)
    context.setContextProperty("logService", log_service)
    context.setContextProperty("transcriptionService", transcription_service)
    context.setContextProperty("alignmentService", alignment_service)

    qml_path = Path(PROJECT_DIR) / "qml" / "App.qml"
    engine.load(qml_path.as_uri())

    if not engine.rootObjects():
        log_service.shutdown()
        return 1

    logger.info("QwenASR GUI 启动完成")
    app.aboutToQuit.connect(application_service.shutdown)
    app.aboutToQuit.connect(log_service.shutdown)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
