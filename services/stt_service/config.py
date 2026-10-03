import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class Config:
    PORT = int(os.getenv("STT_PORT", 8004))
    # Available model sizes: 'tiny.en', 'base.en', 'small.en', 'medium.en', 'large-v3-turbo'
    MODEL_SIZE = os.getenv("WHISPER_MODEL", "small.en")
    DEVICE = os.getenv("WHISPER_DEVICE", "auto")
    COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "default")
    DOWNLOAD_ROOT = str((PROJECT_ROOT / "models" / "whisper").resolve())
