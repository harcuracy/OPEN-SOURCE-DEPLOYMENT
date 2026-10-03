import tempfile
import logging
from pathlib import Path
from flask import Flask, request, jsonify
from waitress import serve

from config import Config
from engine import stt_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [STT_SERVICE] %(levelname)s: %(message)s"
)
logger = logging.getLogger("stt_service")

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify({
        "service": "stt_service",
        "engine": "faster-whisper",
        "model": Config.MODEL_SIZE,
        "device": Config.DEVICE,
        "status": "ok"
    })


@app.post("/transcribe")
def transcribe():
    """
    Accepts:
      - Multipart form-data with file field: 'file'
      - Raw audio bytes in request body
    Returns:
      JSON: {"text": "...", "duration": ..., "language": ...}
    """
    tmp_path = None

    if "file" in request.files:
        audio_file = request.files["file"]
        suffix = Path(audio_file.filename).suffix or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            audio_file.save(tmp.name)
            tmp_path = tmp.name
    elif request.data:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(request.data)
            tmp_path = tmp.name
    else:
        return jsonify({"error": "No audio file provided in 'file' form-data or request body"}), 400

    language = request.form.get("language") or request.args.get("language")

    try:
        result = stt_engine.transcribe(tmp_path, language=language)
        return jsonify(result)
    except Exception as e:
        logger.error("Transcription error: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            if tmp_path and Path(tmp_path).exists():
                Path(tmp_path).unlink()
        except Exception:
            pass


if __name__ == "__main__":
    logger.info("Starting Faster-Whisper STT Microservice on port %d...", Config.PORT)
    serve(app, host="0.0.0.0", port=Config.PORT)
