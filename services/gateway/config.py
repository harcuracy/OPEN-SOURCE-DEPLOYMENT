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

    # Optional dedicated downstream URLs per model (for multi-pod / distributed GPU clusters)
    MODEL_ROUTES = {
        "mistral-7b": os.getenv("MODEL_MISTRAL_URL", "").strip(),
        "qwen-coder": os.getenv("MODEL_CODER_URL", "").strip(),
        "phi-3-mini": os.getenv("MODEL_FAST_URL", "").strip(),
    }

    @classmethod
    def get_llm_url(cls, model_name: str) -> str:
        """Returns dedicated GPU pod URL if configured for this model, else default LLM_SERVICE_URL."""
        url = cls.MODEL_ROUTES.get(model_name)
        if url:
            return url
        for k, v in cls.MODEL_ROUTES.items():
            if k.lower() == model_name.lower() and v:
                return v
        return cls.LLM_SERVICE_URL
