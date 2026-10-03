import logging
from flask import Flask, request, jsonify
from waitress import serve

from config import Config
from engine import engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [LLM_SERVICE] %(levelname)s: %(message)s"
)
logger = logging.getLogger("llm_service")

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify({
        "service": "llm_service",
        "status": "ok",
        "loaded_models": list(engine.loaded_models.keys()),
        "available_models": engine.list_available_models()
    })


@app.get("/models")
def list_models():
    """Lists all models available on the server."""
    return jsonify({
        "models": engine.list_available_models()
    })


@app.post("/generate")
def generate():
    """
    Internal generation endpoint.
    Payload:
      {
        "model": "mistral-7b",
        "messages": [...],
        "max_tokens": 512,
        "temperature": 0.7
      }
    """
    body = request.get_json(silent=True) or {}
    messages = body.get("messages")
    model_name = body.get("model") or Config.DEFAULT_MODEL

    if not isinstance(messages, list) or not messages:
        return jsonify({"error": "'messages' array is required"}), 400

    max_tokens = int(body.get("max_tokens", 512))
    temperature = float(body.get("temperature", 0.7))

    try:
        result = engine.generate(
            model_name=model_name,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        return jsonify(result)

    except Exception as e:
        logger.error("Generation failure on model '%s': %s", model_name, e, exc_info=True)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    logger.info("Starting LLM Microservice on port %d...", Config.PORT)
    serve(app, host="0.0.0.0", port=Config.PORT)
