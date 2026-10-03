# The Complete Codebase & Debugging Manual

Welcome to the internal engineering guide for the **Voice AI Microservices Platform**. 

This document explains **every single file in the codebase**, how the components communicate, how data flows through the system, and **how to debug each file independently** if anything fails in production.

---

## Table of Contents

1. [High-Level Architecture & Data Flow](#1-high-level-architecture--data-flow)
2. [Root Files & Orchestration](#2-root-files--orchestration)
   - [run_microservices.py](#run_microservicespy)
   - [.env & .env.example](#env--envexample)
   - [test_api.ps1](#test_apips1)
   - [runpod_setup.sh](#runpod_setupsh)
   - [docker-compose.yml](#docker-composeyml)
3. [Service 1: API Gateway (Port 8000)](#3-service-1-api-gateway-port-8000)
   - [services/gateway/app.py](#servicesgatewayapppy)
   - [services/gateway/config.py](#servicesgatewayconfigpy)
   - [services/gateway/auth.py](#servicesgatewayauthpy)
   - [services/gateway/routes.py](#servicesgatewayroutespy)
4. [Service 2: LLM Microservice (Port 8002)](#4-service-2-llm-microservice-port-8002)
   - [services/llm_service/app.py](#servicesllm_serviceapppy)
   - [services/llm_service/config.py](#servicesllm_serviceconfigpy)
   - [services/llm_service/engine.py](#servicesllm_serviceenginepy)
5. [Service 3: Kokoro TTS Microservice (Port 8003)](#5-service-3-kokoro-tts-microservice-port-8003)
   - [services/tts_service/app.py](#servicestts_serviceapppy)
   - [services/tts_service/config.py](#servicestts_serviceconfigpy)
   - [services/tts_service/engine.py](#servicestts_serviceenginepy)
6. [Service 4: Faster-Whisper STT Microservice (Port 8004)](#6-service-4-faster-whisper-stt-microservice-port-8004)
   - [services/stt_service/app.py](#servicesstt_serviceapppy)
   - [services/stt_service/config.py](#servicesstt_serviceconfigpy)
   - [services/stt_service/engine.py](#servicesstt_serviceenginepy)
7. [The Master Debugging Matrix](#7-the-master-debugging-matrix)

---

## 1. High-Level Architecture & Data Flow

```text
 Client / Frontend App
         │
         │ HTTP Request with Authorization: Bearer <API_KEY>
         ▼
 ┌─────────────────────────────────────────────────────────────┐
 │                 API Gateway (Port 8000)                     │
 │  • auth.py: Checks API key                                  │
 │  • routes.py: Determines target microservice URL            │
 └───────┬──────────────────────┬──────────────────────┬───────┘
         │                      │                      │
   /v1/chat/completions   /v1/audio/speech    /v1/audio/transcriptions
         │                      │                      │
         ▼                      ▼                      ▼
 ┌───────────────┐      ┌───────────────┐      ┌───────────────┐
 │  LLM Service  │      │  TTS Service  │      │  STT Service  │
 │  (Port 8002)  │      │  (Port 8003)  │      │  (Port 8004)  │
 │ llama.cpp/GGUF│      │ Kokoro ONNX   │      │ Faster-Whisper│
 └───────────────┘      └───────────────┘      └───────────────┘
```

### The 3 Core Invariants:
1. **The Gateway is the ONLY public service.** Downstream workers (LLM, TTS, STT) can run on private network ports, local loopback, or internal cloud VPCs.
2. **Every service is an independent HTTP application.** You can test, restart, or upgrade any service without taking down the others.
3. **OpenAI Compatibility.** The request and response JSON schemas strictly mirror official OpenAI APIs, so any OpenAI frontend SDK connects out-of-the-box.

---

## 2. Root Files & Orchestration

### `run_microservices.py`
- **What it does:** Starts all 4 microservices simultaneously in separate subprocesses. It automatically detects the virtual environment Python (`appgguf/Scripts/python.exe` on Windows or system Python on Linux).
- **How it works:**
  - Iterates through the list of 4 services.
  - Spawns each with `subprocess.Popen(cmd, cwd=service_dir)`.
  - Catches `SIGINT` (Ctrl+C) to gracefully terminate all child processes together.
- **Debugging Tip:** If one service fails to start, don't use `run_microservices.py` to debug it. Run that specific service directly by entering its folder:
  ```bash
  cd services/llm_service && python app.py
  ```

---

### `.env` & `.env.example`
- **What it does:** The single source of truth for ports, paths, GPU layer counts, and keys across the entire project.
- **How it works:** Each service loads this file via `python-dotenv`:
  ```python
  PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
  load_dotenv(PROJECT_ROOT / ".env")
  ```
- **Crucial Keys to Know:**
  - `MODEL_N_GPU_LAYERS=33` — Offloads model layers to your GPU VRAM. (Set to `0` for CPU only, or `-1` / `33` for GPU).
  - `LLM_SERVICE_URL=http://127.0.0.1:8002` — Tells the Gateway where the LLM is. If the LLM is on RunPod, change this to your RunPod proxy URL (`https://<pod_id>-8002.proxy.runpod.net`).
  - `API_KEY=tingo-master-key-...` — The master bearer token protecting your Gateway.

---

### `test_api.ps1`
- **What it does:** Automated end-to-end smoke test script for PowerShell.
- **How it works:**
  1. Calls `GET /health` to verify all 4 services are reporting status `"ok"`.
  2. Calls `GET /v1/models` to ensure all active LLMs, Kokoro, and Whisper are visible.
  3. Sends a prompt to `POST /v1/chat/completions`.
  4. Takes the LLM answer and sends it to `POST /v1/audio/speech` (saves `kokoro_test.wav`).
  5. Sends `kokoro_test.wav` to `POST /v1/audio/transcriptions` to verify that Whisper transcribes it back to text.

---

### `runpod_setup.sh`
- **What it does:** A one-click automated bash script to set up a brand new RunPod GPU Pod.
- **How it works:**
  - Installs system libraries (`ffmpeg`, `espeak-ng`, `build-essential`).
  - Installs pre-compiled CUDA 12 `llama-cpp-python` wheels directly.
  - Automatically copies `.env.example` to `.env` if `.env` doesn't exist.
  - Automatically downloads Kokoro weights into `models/kokoro/`.
  - Runs `nvidia-smi` to detect GPU VRAM and sets `MODEL_N_GPU_LAYERS=33`.

---

### `docker-compose.yml`
- **What it does:** Containerizes all 4 microservices into Docker images with NVIDIA GPU hardware reservations.
- **How it works:**
  - Mounts `./models:/app/models` into the containers so heavy weights don't bloat the Docker images.
  - Contains `deploy.resources.reservations.devices` with `driver: nvidia`, passing host GPUs directly to the containers.

---

## 3. Service 1: API Gateway (Port 8000)

The Gateway is the front door of your system.

### `services/gateway/config.py`
- **What it does:** Reads Gateway settings from `.env`.
- **Key Code:**
  ```python
  MODEL_ROUTES = {
      "mistral-7b": os.getenv("MODEL_MISTRAL_URL", "").strip(),
      "qwen-coder": os.getenv("MODEL_CODER_URL", "").strip(),
      "phi-3-mini": os.getenv("MODEL_FAST_URL", "").strip(),
  }
  ```
  `get_llm_url(model_name)`: Checks if a model has a dedicated remote URL (for multi-pod setups). If not, falls back to the default `LLM_SERVICE_URL`.

### `services/gateway/auth.py`
- **What it does:** Implements the `@require_api_key` security decorator.
- **How it works:**
  - Reads the `Authorization` header from incoming requests.
  - Extracts the Bearer token (`Authorization: Bearer <TOKEN>`).
  - If `Config.API_KEY` is set and the token does not match, returns `401 Unauthorized` in OpenAI's JSON error format.
  - If `Config.API_KEY` is empty, authentication is bypassed (development mode).

### `services/gateway/routes.py`
- **What it does:** Defines the public REST endpoints and proxies payloads to internal microservices using Python's `requests` library.
- **Key Endpoints:**
  - `GET /health` — Concurrently pings `LLM_SERVICE_URL/health`, `TTS_SERVICE_URL/health`, and `STT_SERVICE_URL/health`. If any service is down, it shows which one is unreachable.
  - `GET /v1/models` — Queries the LLM service for available models, adds `kokoro` and `whisper-1`, and returns an OpenAI model list.
  - `POST /v1/chat/completions` — Resolves the destination URL for the requested model and forwards the JSON payload to `/generate`.
  - `POST /v1/audio/speech` — Forwards the text to `TTS_SERVICE_URL/synthesize` and streams the binary WAV audio back to the client.
  - `POST /v1/audio/transcriptions` — Forwards multipart audio files to `STT_SERVICE_URL/transcribe` and returns JSON with transcription text and timestamps.

### `services/gateway/app.py`
- **What it does:** Initializes the Flask application, registers the Blueprint routes, and runs the production WSGI server (`waitress.serve`).

---

## 4. Service 2: LLM Microservice (Port 8002)

The brain of the system. Manages GGUF quantized models with smart memory offloading.

### `services/llm_service/config.py`
- **What it does:** Reads LLM engine parameters.
- **Key Settings:**
  - `MODELS_DIR` — Where `.gguf` files live (defaults to `./models`).
  - `MAX_LOADED_MODELS` — Number of models to keep in VRAM simultaneously (default: `2`).
  - `MODEL_N_GPU_LAYERS` — Defaults to `-1` (all layers on GPU) or `33`.
  - `MODEL_GPUS` — Maps model names to physical GPU IDs (`0`, `1`, `2`) for multi-GPU pods.

### `services/llm_service/engine.py`
- **What it does:** Implements `MultiModelEngine`.
- **Core Concepts:**
  1. **Auto-Discovery (`discover_models`):**
     Scans `models/*.gguf`. Any `.gguf` file placed in the directory is automatically registered using its filename as the model ID without restarting the server.
  2. **LRU Cache (`load_model`):**
     Uses `collections.OrderedDict`. When a model is requested:
     - If already loaded, marks it as recently used via `move_to_end()`.
     - If not loaded and cache is full (`len >= MAX_LOADED_MODELS`), it pops the oldest model using `popitem(last=False)` and frees its memory (`del oldest_instance`).
  3. **Native GGUF Chat Templates (`create_chat_completion`):**
     Instead of guessing prompt syntax, it calls `llm.create_chat_completion(messages=messages)`. `llama-cpp-python` reads the model's embedded Jinja chat template directly from the `.gguf` header, ensuring 100% prompt accuracy.
  4. **Multi-GPU Pinning (`main_gpu`):**
     If running on a multi-GPU pod, sets `main_gpu=target_gpu` so Mistral runs on GPU 0 and Qwen runs on GPU 1.
  5. **Optional Safetensors Engine:**
     Contains a ready-to-uncomment `HuggingFaceSafetensorsEngine` at the bottom for running raw Hugging Face FP16 checkpoints via PyTorch `transformers`.

### `services/llm_service/app.py`
- **Endpoints:**
  - `GET /health` — Returns status and currently loaded models.
  - `GET /models` — Returns list of all discovered models on disk.
  - `POST /generate` — Executes token generation and returns tokens and usage counts.

---

## 5. Service 3: Kokoro TTS Microservice (Port 8003)

High-speed text-to-speech engine running Kokoro-82M under ONNX Runtime.

### `services/tts_service/config.py`
- Points to `models/kokoro/kokoro-v0_19.onnx` (the neural network) and `models/kokoro/voices-v1.0.bin` (the 54 voice vectors).

### `services/tts_service/engine.py`
- **Core Concepts:**
  1. **Auto-Download:** If the `.onnx` or `.bin` files are missing from disk, `load()` automatically downloads them from GitHub releases so the server never crashes on a clean deployment.
  2. **Voice Synthesis (`synthesize`):**
     - Passes text and voice name (`af_heart`, `am_adam`, etc.) to `kokoro.create()`.
     - Kokoro outputs raw audio float samples and sample rate (24,000 Hz).
     - Writes the raw samples to an in-memory `io.BytesIO()` buffer using `soundfile.write(..., format="WAV")`.
     - Returns pure binary WAV bytes.
  3. **Optional Safetensors Engine:**
     Contains a commented-out `PyTorchKokoroSafetensorsEngine` using native PyTorch `KPipeline`.

### `services/tts_service/app.py`
- **Endpoints:**
  - `GET /health` — Verifies model and voice files are present.
  - `GET /voices` — Returns the list of 54 available voice names.
  - `POST /synthesize` — Receives `{"input": "text", "voice": "af_heart"}` and returns `audio/wav` stream.

---

## 6. Service 4: Faster-Whisper STT Microservice (Port 8004)

High-speed speech-to-text engine powered by CTranslate2.

### `services/stt_service/config.py`
- Reads `WHISPER_MODEL_SIZE` (`small.en`, `base.en`, `large-v3`).
- Defaults `WHISPER_DEVICE` to `auto` and `COMPUTE_TYPE` to `default`.

### `services/stt_service/engine.py`
- **Core Concepts:**
  1. **Hardware Detection:** If `torch.cuda.is_available()`, sets `device="cuda"` and `compute_type="float16"`. Otherwise, falls back cleanly to `device="cpu"` and `compute_type="int8"`.
  2. **Transcription (`transcribe`):**
     - Feeds the audio file path into `model.transcribe(beam_size=5)`.
     - Iterates through segments to extract start/end timestamps and transcribed text chunks.
     - Returns full text, language detected, and timestamp segments.
  3. **Optional Safetensors Engine:**
     Contains a commented-out `HuggingFaceSafetensorsSTTEngine` using the standard Hugging Face `transformers` ASR pipeline.

### `services/stt_service/app.py`
- **Endpoints:**
  - `GET /health` — Returns active device (cuda/cpu) and model size.
  - `POST /transcribe` — Receives uploaded audio file from `multipart/form-data`, saves it temporarily to a secure tempfile, calls `transcribe()`, deletes the tempfile, and returns JSON.

---

## 7. The Master Debugging Matrix

When something breaks, use this table to immediately identify the issue:

| Symptom / Error | Which Service | Root Cause | Solution |
| :--- | :--- | :--- | :--- |
| **`502 Bad Gateway` on RunPod** | Any | The Python process crashed inside the container | Check the terminal where `app.py` was running to read the crash traceback. |
| **`Segmentation fault (core dumped)`** | `llm_service` | Model running on CPU with CUDA initialized (`gpu_layers=0`) | In `.env`, set `MODEL_N_GPU_LAYERS=33` (or `-1`) so the model offloads to GPU VRAM. |
| **`Cannot uninstall blinker`** | All | Ubuntu system apt package conflict | Run `pip install --ignore-installed blinker`. |
| **`Kokoro synthesis failed: FileNotFoundError`** | `tts_service` | Model or voice weights missing | Our engine auto-downloads them now, or run `bash runpod_setup.sh`. |
| **`RuntimeError: espeak not found`** | `tts_service` | Linux missing phonemizer system library | In your Linux terminal, run `apt-get install -y espeak-ng`. |
| **`CUDA out of memory (OOM)`** | `llm_service` | Model exceeds GPU VRAM | In `.env`, lower `MODEL_N_CTX` (e.g. from 8192 to 4096) or reduce `MAX_LOADED_MODELS=1`. |
| **`Connection refused: Port 8000`** | `gateway` | Gateway process is not running | Run `python services/gateway/app.py`. |
| **`Unreachable upstream service` in `/health`** | `gateway` | Downstream URL mismatch in `.env` | Verify `LLM_SERVICE_URL`, `TTS_SERVICE_URL`, and `STT_SERVICE_URL` in `.env` match the actual listening ports. |

---

## 8. How to Test Each Service in Isolation

Never test the whole system at once when debugging. Test the broken piece alone:

### 1. Test Gateway:
```bash
curl http://127.0.0.1:8000/health
```

### 2. Test LLM directly (bypass Gateway):
```bash
curl -X POST http://127.0.0.1:8002/generate \
  -H "Content-Type: application/json" \
  -d '{"model": "mistral-7b", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 10}'
```

### 3. Test Kokoro directly (bypass Gateway):
```bash
curl -X POST http://127.0.0.1:8003/synthesize \
  -H "Content-Type: application/json" \
  -d '{"input": "Testing Kokoro sound."}' \
  --output test.wav
```

### 4. Test Faster-Whisper directly (bypass Gateway):
```bash
curl -X POST http://127.0.0.1:8004/transcribe \
  -F "file=@test.wav"
```
