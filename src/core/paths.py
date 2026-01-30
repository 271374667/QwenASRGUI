from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent.parent

MODELS_DIR = PROJECT_DIR / "models"
FORCED_ALIGNER_MODEL_DIR = MODELS_DIR / "Qwen3-ForcedAligner-0.6B"
ASR_MODEL_DIR = MODELS_DIR / "Qwen3-ASR-1.7B"