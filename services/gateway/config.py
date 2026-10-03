import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class Config:
    PORT = int(os.getenv("GATEWAY_PORT", 8000))
    API_KEY = os.getenv("API_KEY", "").strip()
    RATE_LIMIT = os.getenv("RATE_LIMIT", "60/minute")

    # Downstream Microservice URLs
    LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "http://127.0.0.1:8002")
    TTS_SERVICE_URL = os.getenv("TTS_SERVICE_URL", "http://127.0.0.1:8003")
    STT_SERVICE_URL = os.getenv("STT_SERVICE_URL", "http://127.0.0.1:8004")
