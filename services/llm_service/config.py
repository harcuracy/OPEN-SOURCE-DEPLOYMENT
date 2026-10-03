import os
from pathlib import Path
from dotenv import load_dotenv

# Project root directory (3 levels up: services/llm_service -> services -> root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def resolve_path(p: str) -> Path:
    path_obj = Path(p)
    return path_obj if path_obj.is_absolute() else (PROJECT_ROOT / path_obj).resolve()


class Config:
    PORT = int(os.getenv("LLM_PORT", 8002))

    # Inference settings
    N_CTX = int(os.getenv("MODEL_N_CTX", 4096))
    N_THREADS = int(os.getenv("MODEL_N_THREADS", 8))
    N_GPU_LAYERS = int(os.getenv("MODEL_N_GPU_LAYERS", 0))
    N_BATCH = int(os.getenv("MODEL_N_BATCH", 256))

    # Maximum number of models to keep in VRAM/RAM simultaneously (evicts least recently used)
    MAX_LOADED_MODELS = int(os.getenv("MAX_LOADED_MODELS", 2))

    # Models directory
    MODELS_DIR = resolve_path(os.getenv("MODELS_DIR", "./models"))

    # Explicit 3 Model Registrations (can be overridden via .env)
    MODELS = {
        "mistral-7b": str(resolve_path(os.getenv("MODEL_MISTRAL_PATH", "./models/mistral-7b-instruct-v0.2.Q4_K_M.gguf"))),
        "qwen-coder": str(resolve_path(os.getenv("MODEL_CODER_PATH", "./models/qwen2.5-coder-7b-instruct.Q4_K_M.gguf"))),
        "phi-3-mini": str(resolve_path(os.getenv("MODEL_FAST_PATH", "./models/phi-3-mini-4k-instruct.Q4_K_M.gguf"))),
    }
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "mistral-7b")
