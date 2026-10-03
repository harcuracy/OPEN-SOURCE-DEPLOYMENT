import os
import logging
from pathlib import Path
from config import Config

logger = logging.getLogger("stt_service")


class STTEngine:
    def __init__(self):
        self.model = None

    def load(self):
        if self.model is not None:
            return self.model

        from faster_whisper import WhisperModel

        device = Config.DEVICE
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except Exception:
                device = "cpu"

        compute_type = Config.COMPUTE_TYPE
        if compute_type == "default":
            compute_type = "float16" if device == "cuda" else "int8"

        os.makedirs(Config.DOWNLOAD_ROOT, exist_ok=True)

        logger.info("Loading Faster-Whisper '%s' on device=%s (%s)...",
                    Config.MODEL_SIZE, device, compute_type)

        self.model = WhisperModel(
            model_size_or_path=Config.MODEL_SIZE,
            device=device,
            compute_type=compute_type,
            download_root=Config.DOWNLOAD_ROOT
        )

        logger.info("Faster-Whisper model ready for audio transcriptions.")
        return self.model

    def transcribe(self, audio_file_path: str, language: str = None) -> dict:
        """Transcribes an audio file into text."""
        model = self.load()

        segments, info = model.transcribe(
            audio_file_path,
            language=language or "en",
            beam_size=5
        )

        text_pieces = []
        segment_data = []

        for seg in segments:
            text_pieces.append(seg.text)
            segment_data.append({
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": seg.text.strip()
            })

        full_text = " ".join(text_pieces).strip()
        return {
            "text": full_text,
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "duration": round(info.duration, 2),
            "segments": segment_data
        }


stt_engine = STTEngine()


# ==============================================================================
# OPTIONAL SAFETENSORS STT ENGINE (Hugging Face / PyTorch Whisper)
# To use raw Safetensors speech-to-text models directly:
# 1. Install dependencies:
#    pip install torch transformers accelerate torchaudio
# 2. Set WHISPER_MODEL_SIZE in .env to a HF model ID (e.g. 'openai/whisper-small')
#    or a local directory containing 'model.safetensors' & 'config.json'.
# 3. Swap the active engine instance:
#    # stt_engine = STTEngine()
#    stt_engine = HuggingFaceSafetensorsSTTEngine()
# ==============================================================================
# import torch
# from transformers import pipeline
#
# class HuggingFaceSafetensorsSTTEngine:
#     """Direct PyTorch Safetensors Whisper STT loader."""
#     def __init__(self):
#         self.pipe = None
#
#     def load(self):
#         if self.pipe is not None:
#             return self.pipe
#
#         device = 0 if torch.cuda.is_available() else -1
#         torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
#
#         logger.info("Loading Safetensors Whisper model from %s...", Config.MODEL_SIZE)
#         self.pipe = pipeline(
#             "automatic-speech-recognition",
#             model=Config.MODEL_SIZE,
#             torch_dtype=torch_dtype,
#             device=device
#         )
#         return self.pipe
#
#     def transcribe(self, audio_file_path: str, language: str = None) -> dict:
#         pipe = self.load()
#         generate_kwargs = {}
#         if language:
#             generate_kwargs["language"] = language
#
#         result = pipe(
#             audio_file_path,
#             return_timestamps=True,
#             generate_kwargs=generate_kwargs
#         )
#
#         text = (result.get("text") or "").strip()
#         chunks = result.get("chunks", [])
#         segments = []
#         for chunk in chunks:
#             ts = chunk.get("timestamp", (0.0, 0.0))
#             segments.append({
#                 "start": round(ts[0] or 0.0, 2),
#                 "end": round(ts[1] or 0.0, 2),
#                 "text": (chunk.get("text") or "").strip()
#             })
#
#         return {
#             "text": text,
#             "language": language or "en",
#             "language_probability": 1.0,
#             "duration": segments[-1]["end"] if segments else 0.0,
#             "segments": segments
#         }
