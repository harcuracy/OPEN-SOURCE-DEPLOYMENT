import time
import logging
import requests
from flask import Blueprint, request, jsonify, Response

from config import Config
from auth import require_api_key

logger = logging.getLogger("gateway")
api = Blueprint("api", __name__)


# ==============================================================================
# 1. Health Check (Aggregated Across All 4 Microservices)
# ==============================================================================
@api.get("/health")
def health():
    """Aggregated health check across Gateway, LLM, Kokoro TTS, and Faster-Whisper STT."""
    health_status = {
        "gateway": "ok",
        "llm_service": "unknown",
        "tts_service": "unknown",
        "stt_service": "unknown"
    }

    try:
        r = requests.get(f"{Config.LLM_SERVICE_URL}/health", timeout=2)
        health_status["llm_service"] = r.json() if r.status_code == 200 else f"error_{r.status_code}"
    except Exception as e:
        health_status["llm_service"] = f"unreachable: {e}"

    try:
        r = requests.get(f"{Config.TTS_SERVICE_URL}/health", timeout=2)
        health_status["tts_service"] = r.json() if r.status_code == 200 else f"error_{r.status_code}"
    except Exception as e:
        health_status["tts_service"] = f"unreachable: {e}"

    try:
        r = requests.get(f"{Config.STT_SERVICE_URL}/health", timeout=2)
        health_status["stt_service"] = r.json() if r.status_code == 200 else f"error_{r.status_code}"
    except Exception as e:
        health_status["stt_service"] = f"unreachable: {e}"

    return jsonify(health_status)


# ==============================================================================
# 2. Models Listing (OpenAI Format)
# ==============================================================================
@api.get("/v1/models")
@require_api_key
def list_models():
    """Returns all LLM, TTS, and STT models."""
    try:
        resp = requests.get(f"{Config.LLM_SERVICE_URL}/models", timeout=5)
        model_names = resp.json().get("models", []) if resp.status_code == 200 else []
    except Exception:
        model_names = ["mistral-7b"]

    models_data = [
        {"id": m, "object": "model", "owned_by": "local-llm"} for m in model_names
    ]
    models_data.append({"id": "kokoro", "object": "model", "owned_by": "local-tts"})
    models_data.append({"id": "whisper-1", "object": "model", "owned_by": "local-stt"})

    return jsonify({
        "object": "list",
        "data": models_data
    })


# ==============================================================================
# 3. Chat Completions (LLM Microservice)
# ==============================================================================
@api.post("/v1/chat/completions")
@require_api_key
def chat_completions():
    body = request.get_json(silent=True) or {}
    messages = body.get("messages")
    model_name = body.get("model", "mistral-7b")

    if not isinstance(messages, list) or not messages:
        return jsonify({"error": {"message": "'messages' array is required", "type": "invalid_request_error"}}), 400

    if body.get("stream", False):
        return jsonify({"error": {"message": "Streaming is not supported in current mode", "type": "not_implemented"}}), 501

    payload = {
        "model": model_name,
        "messages": messages,
        "max_tokens": int(body.get("max_tokens", 512)),
        "temperature": float(body.get("temperature", 0.7))
    }

    target_llm_url = Config.get_llm_url(model_name)
    try:
        resp = requests.post(f"{target_llm_url}/generate", json=payload, timeout=180)
        if resp.status_code != 200:
            err = resp.json() if resp.headers.get("content-type") == "application/json" else {"error": resp.text}
            return jsonify({"error": {"message": err.get("error", "LLM service error"), "type": "upstream_error"}}), resp.status_code

        llm_data = resp.json()
        content = llm_data.get("text", "")
        prompt_tokens = llm_data.get("prompt_tokens", 0)
        completion_tokens = llm_data.get("completion_tokens", 0)

        return jsonify({
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
        })

    except requests.exceptions.RequestException as e:
        logger.error("Error communicating with LLM microservice: %s", e)
        return jsonify({"error": {"message": f"LLM microservice unreachable: {e}", "type": "gateway_timeout"}}), 504


# ==============================================================================
# 4. Text-To-Speech (Kokoro TTS Microservice)
# ==============================================================================
@api.post("/v1/audio/speech")
@require_api_key
def audio_speech():
    """
    OpenAI-Compatible Speech Endpoint:
    POST /v1/audio/speech
    Body: {"model": "kokoro", "input": "text", "voice": "af_heart"}
    """
    body = request.get_json(silent=True) or {}
    text = (body.get("input") or "").strip()
    voice = body.get("voice", "af_heart")
    speed = float(body.get("speed", 1.0))

    if not text:
        return jsonify({"error": {"message": "'input' text is required", "type": "invalid_request_error"}}), 400

    try:
        resp = requests.post(f"{Config.TTS_SERVICE_URL}/synthesize", json={
            "input": text,
            "voice": voice,
            "speed": speed
        }, timeout=60)

        if resp.status_code != 200:
            return jsonify({"error": {"message": "TTS synthesis failed", "type": "upstream_error"}}), resp.status_code

        return Response(resp.content, mimetype="audio/wav")

    except Exception as e:
        logger.error("Error calling TTS microservice: %s", e)
        return jsonify({"error": {"message": f"TTS microservice unreachable: {e}", "type": "gateway_error"}}), 504


@api.get("/v1/audio/voices")
@require_api_key
def list_voices():
    """Lists available Kokoro TTS voices."""
    try:
        resp = requests.get(f"{Config.TTS_SERVICE_URL}/voices", timeout=5)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": {"message": f"TTS microservice unreachable: {e}", "type": "gateway_error"}}), 504


# ==============================================================================
# 5. Speech-To-Text (Faster-Whisper STT Microservice)
# ==============================================================================
@api.post("/v1/audio/transcriptions")
@require_api_key
def audio_transcriptions():
    """
    OpenAI-Compatible Transcription Endpoint:
    POST /v1/audio/transcriptions
    Form Data:
      file: audio file (wav, mp3, m4a, etc.)
      model: "whisper-1" (optional)
      language: "en" (optional)
    Returns:
      {"text": "Transcribed spoken text"}
    """
    if "file" not in request.files and not request.data:
        return jsonify({"error": {"message": "Audio file is required in 'file' field", "type": "invalid_request_error"}}), 400

    files = None
    data = None

    if "file" in request.files:
        uploaded = request.files["file"]
        files = {"file": (uploaded.filename, uploaded.read(), uploaded.content_type)}
        data = {"language": request.form.get("language", "en")}
    else:
        files = {"file": ("audio.wav", request.data, "audio/wav")}

    try:
        resp = requests.post(f"{Config.STT_SERVICE_URL}/transcribe", files=files, data=data, timeout=60)

        if resp.status_code != 200:
            err = resp.json() if resp.headers.get("content-type") == "application/json" else {"error": resp.text}
            return jsonify({"error": {"message": err.get("error", "STT service error"), "type": "upstream_error"}}), resp.status_code

        stt_result = resp.json()
        # Return standard OpenAI transcription schema: {"text": "..."}
        return jsonify({
            "text": stt_result.get("text", ""),
            "duration": stt_result.get("duration"),
            "language": stt_result.get("language")
        })

    except Exception as e:
        logger.error("Error communicating with STT microservice: %s", e)
        return jsonify({"error": {"message": f"STT microservice unreachable: {e}", "type": "gateway_error"}}), 504
