#!/usr/bin/env python3
"""
Download Qwen ASR models into the project's root models directory.

This script expects `modelscope` to be installed and available on PATH.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> None:
    print(f"+ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd), check=True)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))

    from src.core.paths import (  # pylint: disable=import-outside-toplevel
        ASR_MODEL_DIR,
        ASR_SMALL_MODEL_DIR,
        FORCED_ALIGNER_MODEL_DIR,
        MODELS_DIR,
        PROJECT_DIR,
    )

    models_root = MODELS_DIR
    models_root.mkdir(parents=True, exist_ok=True)

    downloads = [
        ("Qwen/Qwen3-ASR-1.7B", ASR_MODEL_DIR),
        ("Qwen/Qwen3-ASR-0.6B", ASR_SMALL_MODEL_DIR),
        ("Qwen/Qwen3-ForcedAligner-0.6B", FORCED_ALIGNER_MODEL_DIR),
    ]

    for model_id, local_dir in downloads:
        run(
            [
                "modelscope",
                "download",
                "--model",
                model_id,
                "--local_dir",
                str(local_dir),
            ],
            cwd=PROJECT_DIR,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
