import logging
from flask import Flask, request, jsonify, Response
from waitress import serve

from config import Config
from engine import tts_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [TTS_SERVICE] %(levelname)s: %(message)s"
)
logger = logging.getLogger("tts_service")

app = Flask(__name__)


@app.get("/health")
def health():
    model_ready = Config.MODEL_PATH.exists() and Config.VOICES_PATH.exists()
    return jsonify({
        "service": "tts_service",
        "engine": "kokoro-onnx",
        "status": "ok",
        "model_files_present": model_ready,
        "default_voice": Config.DEFAULT_VOICE
    })


@app.get("/voices")
def get_voices():
    try:
        tts_engine.load()
        return jsonify({"voices": tts_engine.voices})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/synthesize")
def synthesize():
    """
    Accepts:
      {
        "input": "Text to read aloud",
        "voice": "af_heart",
        "speed": 1.0
      }
    Returns:
      audio/wav binary stream
    """
    data = request.get_json(silent=True) or {}
    text = (data.get("input") or data.get("text") or "").strip()
    voice = data.get("voice", Config.DEFAULT_VOICE)
    speed = float(data.get("speed", Config.DEFAULT_SPEED))

    if not text:
        return jsonify({"error": "'input' text is required"}), 400

    try:
        wav_bytes = tts_engine.synthesize(text=text, voice=voice, speed=speed)
        return Response(wav_bytes, mimetype="audio/wav")
    except Exception as e:
        logger.error("Synthesis failed: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    logger.info("Starting Kokoro TTS Microservice on port %d...", Config.PORT)
    serve(app, host="0.0.0.0", port=Config.PORT)
