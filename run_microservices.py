import sys
import subprocess
import time
import signal
import os

venv_python = os.path.abspath("appgguf/Scripts/python.exe")
python_bin = venv_python if os.path.exists(venv_python) else sys.executable

services = [
    {
        "name": "Faster-Whisper STT (Port 8004)",
        "cwd": os.path.abspath("services/stt_service"),
        "cmd": [python_bin, "app.py"]
    },
    {
        "name": "Kokoro TTS Service (Port 8003)",
        "cwd": os.path.abspath("services/tts_service"),
        "cmd": [python_bin, "app.py"]
    },
    {
        "name": "LLM Service (Port 8002)",
        "cwd": os.path.abspath("services/llm_service"),
        "cmd": [python_bin, "app.py"]
    },
    {
        "name": "API Gateway (Port 8000)",
        "cwd": os.path.abspath("services/gateway"),
        "cmd": [python_bin, "app.py"]
    }
]

processes = []

def stop_all(sig=None, frame=None):
    print("\nShutting down all microservices...")
    for p in processes:
        p.terminate()
    sys.exit(0)

signal.signal(signal.SIGINT, stop_all)

print("Starting Voice AI Microservices (Gateway + LLM + TTS + STT)...")
for s in services:
    print(f"Launching {s['name']}...")
    p = subprocess.Popen(s["cmd"], cwd=s["cwd"])
    processes.append(p)
    time.sleep(1)

print("\nAll 4 microservices active!")
print("Gateway API URL:          http://127.0.0.1:8000")
print("Health Check:             http://127.0.0.1:8000/health")
print("OpenAI Chat:              http://127.0.0.1:8000/v1/chat/completions")
print("OpenAI Kokoro Speech:      http://127.0.0.1:8000/v1/audio/speech")
print("OpenAI Whisper Transcribe: http://127.0.0.1:8000/v1/audio/transcriptions")
print("Press Ctrl+C to stop all services.\n")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    stop_all()
