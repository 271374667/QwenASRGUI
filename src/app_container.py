"""兼容层。

新架构的组合根位于 `src.application.composition_root`。
该文件仅作为旧导入路径的兼容别名保留，避免本地未同步脚本立即失效。
"""

from __future__ import annotations

from src.application.composition_root import CompositionRoot

AppContainer = CompositionRoot
