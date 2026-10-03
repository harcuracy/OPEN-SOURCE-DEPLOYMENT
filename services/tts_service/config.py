import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def resolve_path(p: str) -> Path:
    path_obj = Path(p)
    return path_obj if path_obj.is_absolute() else (PROJECT_ROOT / path_obj).resolve()


class Config:
    PORT = int(os.getenv("TTS_PORT", 8003))
    MODEL_PATH = resolve_path(os.getenv("KOKORO_MODEL_PATH", "./models/kokoro/kokoro-v0_19.onnx"))
    VOICES_PATH = resolve_path(os.getenv("KOKORO_VOICES_PATH", "./models/kokoro/voices-v1.0.bin"))
    DEFAULT_VOICE = os.getenv("KOKORO_DEFAULT_VOICE", "af_heart")
    DEFAULT_SPEED = float(os.getenv("KOKORO_DEFAULT_SPEED", 1.0))
