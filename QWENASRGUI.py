"""QwenASR GUI 启动入口。"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from src.application import CompositionRoot
from src.core.paths import PROJECT_DIR

APP_FONT_FAMILY = "Source Han Sans SC"
APP_FONT_POINT_SIZE = 10.5


def _configure_application_fonts(app: QApplication) -> None:
    """注册并设置应用全局字体。"""
    font_dir = Path(PROJECT_DIR) / "qml" / "Fonts"
    loaded_families: list[str] = []

    if not font_dir.exists():
        logger.warning("字体目录不存在: {}", font_dir)
        return

    for pattern in ("*.otf", "*.ttf"):
        for font_path in sorted(font_dir.glob(pattern)):
            font_id = QFontDatabase.addApplicationFont(str(font_path))
            if font_id == -1:
                logger.warning("字体加载失败: {}", font_path.name)
                continue
            loaded_families.extend(QFontDatabase.applicationFontFamilies(font_id))

    if not loaded_families:
        logger.warning("未能从 {} 加载任何字体文件", font_dir)
        return

    family = (
        APP_FONT_FAMILY
        if APP_FONT_FAMILY in loaded_families
        else loaded_families[0]
    )
    font = app.font()
    font.setFamily(family)
    font.setPointSizeF(APP_FONT_POINT_SIZE)
    font.setWeight(QFont.Normal)
    app.setFont(font)
    logger.info("应用字体已设置为 {} ({:.1f}pt)", family, APP_FONT_POINT_SIZE)


def main() -> int:
    """启动 GUI 应用。"""
    QQuickStyle.setStyle("FluentWinUI3")

    app = QApplication(sys.argv)
    app.setApplicationName("QwenASR")
    app.setOrganizationName("QwenASRGUI")
    _configure_application_fonts(app)

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
