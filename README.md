# Voice AI Microservices Platform — Developer Documentation

A high-performance, modular, self-hosted Voice AI platform implementing official **OpenAI-compatible REST APIs**. 

Designed for low latency, low VRAM consumption, and decoupled horizontal scalability. Each component operates as an isolated microservice that can run together on a single workstation or distributed across multiple cloud GPUs (e.g., RunPod).

---

## 1. System Architecture

```text
                        ┌─────────────────────────────────────┐
                        │   Client Apps / Web UI / Voice Bot  │
                        └──────────────────┬──────────────────┘
                                           │
                         HTTP / Port 8000  ▼
                ┌─────────────────────────────────────────────────────┐
                │                  1. API Gateway                     │
                │        Auth, Rate Limiting, Proxy Dispatch          │
                └──────────────┬──────────────┬──────────────┬────────┘
                               │              │              │
                   Port 8002   ▼  Port 8003   ▼  Port 8004   ▼
        ┌────────────────────────┐  ┌──────────────┐  ┌──────────────────────┐
        │     2. LLM Service     │  │3. TTS Service│  │    4. STT Service    │
        │ llama.cpp / GGUF Multi-│  │  Kokoro-82M  │  │    Faster-Whisper    │
        │ Model LRU Eviction     │  │  (54 Voices) │  │    (CTranslate2)     │
        └────────────────────────┘  └──────────────┘  └──────────────────────┘
```

### Microservice Summary

| Service | Port | Underlying Engine | OpenAI Route | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **API Gateway** | `8000` | Flask / Waitress | `/health`, `/v1/models` | Unified ingress, security, token verification, routing |
| **LLM Service** | `8002` | `llama-cpp-python` (GGUF) | `/v1/chat/completions` | Multi-model chat inference with LRU memory caching |
| **TTS Service** | `8003` | `kokoro-onnx` | `/v1/audio/speech` | Expressive text-to-speech audio synthesis |
| **STT Service** | `8004` | `faster-whisper` | `/v1/audio/transcriptions`| Audio-to-text transcription with timestamp support |

---

## 2. Directory Structure

```text
gguf_openai_server/
│
├── .env                           # Global environment configuration
├── .gitignore                     # Git rules (excludes heavy models & venv)
├── README.md                      # Primary project documentation
├── docker-compose.yml             # Container orchestration with NVIDIA GPU reservations
├── run_microservices.py           # Single-command launcher for all 4 services
├── runpod_setup.sh                # Automated one-click RunPod GPU deployment script
├── test_api.ps1                   # Automated end-to-end verification script
│
├── models/                        # Local model weights directory
│   ├── mistral-7b-*.gguf          # Quantized LLM weights (GGUF format)
│   ├── kokoro/
│   │   ├── kokoro-v0_19.onnx      # Kokoro-82M ONNX model weights (325 MB)
│   │   └── voices-v1.0.bin        # 54 Kokoro voice embedding tensors (28 MB)
│   └── whisper/                   # Download directory for Faster-Whisper weights
│
└── services/
    ├── gateway/                   # Ingress API Gateway (Port 8000)
    │   ├── app.py                 # Service entry point & Waitress HTTP server
    │   ├── auth.py                # Bearer token validation decorator
    │   ├── config.py              # Port, Rate limits, downstream URLs
    │   ├── routes.py              # OpenAI route implementations & proxies
    │   └── requirements.txt
    │
    ├── llm_service/               # Multi-Model LLM Engine (Port 8002)
    │   ├── app.py                 # Flask server
    │   ├── config.py              # Context size, threads, GPU layers, registered models
    │   ├── engine.py              # LRU model cache + auto-discovery + Safetensors alt
    │   └── requirements.txt
    │
    ├── tts_service/               # Kokoro Text-To-Speech (Port 8003)
    │   ├── app.py                 # Flask server
    │   ├── config.py              # Voices path, default voice & speed
    │   ├── engine.py              # Kokoro ONNX synthesis + Safetensors alt
    │   └── requirements.txt
    │
    └── stt_service/               # Faster-Whisper Speech-To-Text (Port 8004)
        ├── app.py                 # Flask server
        ├── config.py              # Model size (small.en), CUDA compute type
        ├── engine.py              # CTranslate2 audio transcription + Safetensors alt
        └── requirements.txt
```

---

## 3. Microservice Deep Dives

### 1. API Gateway (`services/gateway/`)
- **Port:** `8000`
- **Role:** Single public-facing entry point. Isolates downstream AI workers from direct internet exposure.
- **Authentication:** Enforces `Authorization: Bearer <API_KEY>` on all `/v1/*` routes using `auth.py`.
- **Downstream Proxying:** 
  - `POST /v1/chat/completions` ➡️ Proxied to `LLM_SERVICE_URL/generate`.
  - `POST /v1/audio/speech` ➡️ Proxied to `TTS_SERVICE_URL/synthesize` (streams binary WAV).
  - `POST /v1/audio/transcriptions` ➡️ Multipart audio payload forwarded to `STT_SERVICE_URL/transcribe`.
- **Health Aggregator:** `GET /health` pings all three internal microservices concurrently and reports a consolidated status.

### 2. LLM Service (`services/llm_service/`)
- **Port:** `8002`
- **Automatic GGUF Model Discovery:** Scans the `models/` directory for any `.gguf` file and exposes it to `/v1/models` without code modifications.
- **LRU (Least Recently Used) Memory Management:**
  Keeps up to `MAX_LOADED_MODELS` (default: 2) in VRAM/RAM. When a request requests a 3rd model, the oldest inactive model is evicted using Python's `OrderedDict.popitem(last=False)` and deleted, preventing Out-Of-Memory (OOM) crashes.
- **Optional Safetensors Engine:** Contains a commented-out `HuggingFaceSafetensorsEngine` at the bottom of `engine.py` for loading raw Hugging Face FP16 checkpoints via PyTorch `transformers`.

### 3. TTS Service (`services/tts_service/`)
- **Port:** `8003`
- **Engine:** Kokoro-82M running under ONNX Runtime.
- **Voices Matrix:** Loads `models/kokoro/voices-v1.0.bin` (NumPy serialization of 54 distinct voices).
- **Output:** Returns binary `audio/wav` formatted audio (24,000 Hz sample rate) via `soundfile`.
- **Optional Safetensors Engine:** Includes a commented-out `PyTorchKokoroSafetensorsEngine` in `engine.py` to use Kokoro's native PyTorch pipeline if preferred.

### 4. STT Service (`services/stt_service/`)
- **Port:** `8004`
- **Engine:** Faster-Whisper backed by `CTranslate2` (up to 4× faster than vanilla Whisper).
- **Auto Hardware Detection:** Automatically selects `cuda` with `float16` when an NVIDIA GPU is available; falls back cleanly to CPU with `int8` quantization.
- **Output:** Transcribes audio and returns full text along with word/segment timestamps.
- **Optional Safetensors Engine:** Includes a commented-out `HuggingFaceSafetensorsSTTEngine` using the standard Hugging Face `transformers` ASR pipeline.

---

## 4. Configuration & Environment Variables (`.env`)

All four services read from the single root `.env` file:

```env
# ==============================================================================
# Security & Gateway Configuration
# ==============================================================================
GATEWAY_PORT=8000
API_KEY=tingo-master-key-1234567890abcdef
RATE_LIMIT=60/minute

# Downstream Service URLs (Change these when deploying across different Pods)
LLM_SERVICE_URL=http://127.0.0.1:8002
TTS_SERVICE_URL=http://127.0.0.1:8003
STT_SERVICE_URL=http://127.0.0.1:8004

# ==============================================================================
# LLM Microservice Settings
# ==============================================================================
LLM_PORT=8002
MODELS_DIR=./models
MAX_LOADED_MODELS=2
MODEL_N_THREADS=8
MODEL_N_GPU_LAYERS=0            # Set to 33 or 99 on GPU pods to offload to VRAM
MODEL_N_CTX=4096                # Context token length
DEFAULT_MODEL=mistral-7b

# Named Model Path Aliases
MODEL_MISTRAL_PATH=./models/mistral-7b-instruct-v0.2.Q4_K_M.gguf
MODEL_CODER_PATH=./models/qwen2.5-coder-7b-instruct.Q4_K_M.gguf
MODEL_FAST_PATH=./models/phi-3-mini-4k-instruct.Q4_K_M.gguf

# ==============================================================================
# Kokoro TTS Settings
# ==============================================================================
TTS_PORT=8003
KOKORO_MODEL_PATH=./models/kokoro/kokoro-v0_19.onnx
KOKORO_VOICES_PATH=./models/kokoro/voices-v1.0.bin
KOKORO_DEFAULT_VOICE=af_heart   # Default voice: af_heart, am_adam, bf_emma, etc.
KOKORO_DEFAULT_SPEED=1.0

# ==============================================================================
# Faster-Whisper STT Settings
# ==============================================================================
STT_PORT=8004
WHISPER_MODEL_SIZE=small.en     # Options: tiny.en, base.en, small.en, medium.en, large-v3
WHISPER_DEVICE=auto             # auto, cuda, or cpu
WHISPER_COMPUTE_TYPE=default    # default (float16 on GPU, int8 on CPU)
```

---

## 5. Adding & Modifying Models

### Adding a New LLM
1. **Drop-in:** Download any quantized `.gguf` file into `models/`.
2. **Auto-Discovery:** The server immediately lists it in `/v1/models` using the filename as the ID.
3. **Custom Alias (Optional):** Define a short nickname in `services/llm_service/config.py`:
   ```python
   MODELS = {
       "my-model": str(resolve_path("./models/My-Custom-Model.Q4_K_M.gguf")),
   }
   ```

### Changing Whisper STT Model
In `.env`, update `WHISPER_MODEL_SIZE`:
```env
WHISPER_MODEL_SIZE=large-v3
```
On next startup, Faster-Whisper automatically downloads the model weights.

### Selecting Kokoro Voices
Kokoro includes 54 built-in voices in `voices-v1.0.bin`. Specify any voice in your API request:
- American Female: `af_heart`, `af_bella`, `af_nicole`, `af_sky`
- American Male: `am_adam`, `am_michael`
- British Female: `bf_emma`, `bf_isabella`
- British Male: `bm_george`, `bm_lewis`

---

## 6. Deployment Workflows

### A. Local Development (Windows)
Run all 4 microservices with the master launcher:
```powershell
.\appgguf\Scripts\python.exe run_microservices.py
```
Run the automated end-to-end test:
```powershell
powershell -ExecutionPolicy Bypass -File .\test_api.ps1
```

---

### B. Single GPU Cloud Deployment (RunPod)
Rent an **RTX 3090 (24GB)** or **RTX 4090**:
1. Choose the **RunPod PyTorch 2.1** template.
2. In the Pod Web Terminal:
   ```bash
   git clone <your_repo_url>
   cd gguf_openai_server
   bash runpod_setup.sh
   python run_microservices.py
   ```
3. RunPod exposes Port 8000 at:
   `https://<POD_ID>-8000.proxy.runpod.net`

---

### C. Multi-GPU on One Pod (e.g. 2x RTX 3090)
Isolate workloads to dedicated physical GPUs:
```bash
# Terminal 1: LLM exclusively on GPU 0
CUDA_VISIBLE_DEVICES=0 python services/llm_service/app.py &

# Terminal 2: STT & TTS shared on GPU 1
CUDA_VISIBLE_DEVICES=1 python services/stt_service/app.py &
CUDA_VISIBLE_DEVICES=1 python services/tts_service/app.py &

# Terminal 3: Gateway on CPU
python services/gateway/app.py &
```

---

### D. Distributed Multi-Pod Setup (Separate GPUs Across Pods)
When running services on different RunPod machines:
1. **Pod 1 (RTX 4090):** Run LLM on Port 8002 ➡️ URL: `https://pod1-8002.proxy.runpod.net`
2. **Pod 2 (Cheap GPU):** Run TTS on Port 8003 ➡️ URL: `https://pod2-8003.proxy.runpod.net`
3. **Pod 3 (T4 GPU):** Run STT on Port 8004 ➡️ URL: `https://pod3-8004.proxy.runpod.net`
4. **Gateway (VPS / Render / Pod 1):** In `.env`, set:
   ```env
   LLM_SERVICE_URL=https://pod1-8002.proxy.runpod.net
   TTS_SERVICE_URL=https://pod2-8003.proxy.runpod.net
   STT_SERVICE_URL=https://pod3-8004.proxy.runpod.net
   ```

---

## 7. API Reference & Code Examples

### 1. Health Check
```bash
curl http://localhost:8000/health
```

### 2. Chat Completions
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer tingo-master-key-1234567890abcdef" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistral-7b",
    "messages": [
      {"role": "user", "content": "Explain quantum computing in one sentence."}
    ],
    "max_tokens": 100
  }'
```

### 3. Speech Synthesis (Text-to-Speech)
```bash
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Authorization: Bearer tingo-master-key-1234567890abcdef" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "kokoro",
    "input": "Voice AI microservices initialized.",
    "voice": "af_heart"
  }' \
  --output voice.wav
```

### 4. Audio Transcription (Speech-to-Text)
```bash
curl -X POST http://localhost:8000/v1/audio/transcriptions \
  -H "Authorization: Bearer tingo-master-key-1234567890abcdef" \
  -F "file=@voice.wav" \
  -F "model=whisper-1"
```

### 5. Official OpenAI Python / JavaScript SDK Integration
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="tingo-master-key-1234567890abcdef"
)

# Chat
response = client.chat.completions.create(
    model="mistral-7b",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)

# TTS
speech = client.audio.speech.create(
    model="kokoro",
    voice="af_heart",
    input="Hello world!"
)
speech.stream_to_file("output.wav")
```
