#!/usr/bin/env bash
# ==============================================================================
# RunPod One-Click Deployment Script for Voice AI Microservices
# Compatible with: RTX 3090, RTX 4090, A40, A5000, A6000, A100, H100
# ==============================================================================

set -e

echo "=== 1. Updating System Dependencies ==="
apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    espeak-ng \
    curl \
    git \
    build-essential

echo "=== 2. Installing Python Packages with CUDA Support ==="
pip install --upgrade pip

# Install prebuilt CUDA 12.1 / 12.2 llama-cpp-python for instant GPU acceleration
pip install llama-cpp-python \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu122 || \
pip install llama-cpp-python \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121 || \
CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python --no-cache-dir

# Install Faster-Whisper, Kokoro TTS, Gateway, and server utilities
# Note: --ignore-installed blinker avoids Ubuntu dist-packages RECORD conflict
pip install --ignore-installed blinker
pip install faster-whisper kokoro-onnx soundfile flask waitress requests python-dotenv

echo "=== 3. Ensuring Model Directories & Kokoro Weights ==="
mkdir -p models/kokoro models/whisper

python - << 'EOF'
import os
import urllib.request
from pathlib import Path

kokoro_model = Path("models/kokoro/kokoro-v0_19.onnx")
kokoro_voices = Path("models/kokoro/voices-v1.0.bin")

if not kokoro_model.exists():
    print("Downloading Kokoro ONNX model (325MB)...")
    url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v0_19.onnx"
    urllib.request.urlretrieve(url, str(kokoro_model))

if not kokoro_voices.exists():
    print("Downloading Kokoro Voices archive (28MB)...")
    url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"
    urllib.request.urlretrieve(url, str(kokoro_voices))

print("Kokoro assets ready.")
EOF

echo "=== 4. GPU Verification ==="
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader
    echo "NVIDIA GPU Detected! Enabling CUDA GPU offloading in .env..."
    sed -i 's/MODEL_N_GPU_LAYERS=0/MODEL_N_GPU_LAYERS=33/g' .env || true
fi

echo ""
echo "Setup complete! You can now start the microservices with:"
echo "    python run_microservices.py"
echo ""
echo "To access from outside RunPod:"
echo "    In RunPod console, expose port 8000 via HTTP Proxy to get your public URL:"
echo "    https://<POD_ID>-8000.proxy.runpod.net/v1/chat/completions"
