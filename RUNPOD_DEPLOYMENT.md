# RunPod Multi-GPU Deployment Guide

This guide explains how to deploy the Voice AI microservices platform across **different GPUs on RunPod**.

Depending on your budget and scaling needs, you can choose between two deployment strategies:

1. **Strategy A: Distributed Multi-Pod Setup** — Each microservice runs on its own independent RunPod instance with a dedicated GPU tier (e.g., A100 for LLM, budget GPU for TTS, T4 for STT).
2. **Strategy B: Multi-GPU Single-Pod Setup** — A single RunPod instance equipped with 2 or 4 GPUs (e.g., 2x RTX 3090), allocating specific GPUs to specific microservices on `localhost`.

---

## Architecture Diagram: Distributed Multi-Pod

```text
                            ┌────────────────────────┐
                            │   Frontend / User App  │
                            └───────────┬────────────┘
                                        │
                       HTTPS (Port 8000)│
                                        ▼
                        ┌────────────────────────────────┐
                        │      API Gateway (Port 8000)   │
                        │   (Runs on cheap CPU / Pod 1)  │
                        └───────┬────────┬────────┬──────┘
                                │        │        │
           https://pod1-8002... │        │        │ https://pod3-8004...
                                ▼        │        ▼
             ┌─────────────────────┐     │     ┌──────────────────────┐
             │ Pod 1: High-End GPU │     │     │  Pod 3: Mid-Tier GPU │
             │   (RTX 4090 / A100) │     │     │      (T4 / 3080)     │
             │   LLM Microservice  │     │     │   Faster-Whisper STT │
             │      (Port 8002)    │     │     │      (Port 8004)     │
             └─────────────────────┘     │     └──────────────────────┘
                                         ▼
                             ┌──────────────────────┐
                             │  Pod 2: Budget GPU   │
                             │  Kokoro TTS (Speech) │
                             │      (Port 8003)     │
                             └──────────────────────┘
                              https://pod2-8003...
```

---

## Strategy A: Distributed Multi-Pod Setup

### Step 1: Deploy Pod 1 — LLM Microservice (High-End GPU)

1. Go to [RunPod.io Console](https://runpod.io/console/pods) and click **Deploy**.
2. Select a high-VRAM GPU:
   - **Recommended:** **RTX 4090 (24 GB)** or **A100 (80 GB)** for 70B models.
3. Select template: **RunPod PyTorch 2.1** (or any Ubuntu CUDA 12 image).
4. Click **Edit Pod Settings** -> In **Expose HTTP Ports**, enter: `8002`.
5. Click **Deploy On-Demand**.
6. When the pod status is *Running*, click **Connect** -> **Start Web Terminal** and run:

```bash
git clone <YOUR_GIT_REPO_URL>
cd gguf_openai_server

# Install dependencies with CUDA acceleration
pip install --upgrade pip
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu122 || \
CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python
pip install flask waitress requests python-dotenv

# Offload all 33 layers to GPU in .env
sed -i 's/MODEL_N_GPU_LAYERS=0/MODEL_N_GPU_LAYERS=33/g' .env

# Start LLM Microservice
python services/llm_service/app.py
```

7. Copy the public URL for Pod 1 from RunPod:
   `https://<POD1_ID>-8002.proxy.runpod.net`

---

### Step 2: Deploy Pod 2 — Kokoro TTS Microservice (Budget GPU / CPU)

Kokoro-82M is extremely lightweight (~0.5 GB VRAM) and synthesizes audio in ~150ms.

1. Click **Deploy** in RunPod.
2. Select a budget GPU (e.g. **RTX 3070 / RTX 3080**) or a **CPU Pod**.
3. Under **Expose HTTP Ports**, enter: `8003`.
4. Open the Web Terminal and run:

```bash
git clone <YOUR_GIT_REPO_URL>
cd gguf_openai_server

# Install TTS dependencies
apt-get update && apt-get install -y espeak-ng ffmpeg
pip install kokoro-onnx soundfile flask waitress requests python-dotenv

# Download Kokoro ONNX model and voices
mkdir -p models/kokoro
curl -L -o models/kokoro/kokoro-v0_19.onnx \
  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v0_19.onnx
curl -L -o models/kokoro/voices-v1.0.bin \
  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin

# Start Kokoro TTS Microservice
python services/tts_service/app.py
```

5. Copy the public URL for Pod 2:
   `https://<POD2_ID>-8003.proxy.runpod.net`

---

### Step 3: Deploy Pod 3 — Faster-Whisper STT Microservice (Mid-Tier GPU)

1. Click **Deploy** in RunPod.
2. Select a mid-tier GPU (e.g. **RTX 3080**, **T4**, or **L4**).
3. Under **Expose HTTP Ports**, enter: `8004`.
4. Open the Web Terminal and run:

```bash
git clone <YOUR_GIT_REPO_URL>
cd gguf_openai_server

# Install STT dependencies
apt-get update && apt-get install -y ffmpeg
pip install faster-whisper flask waitress requests python-dotenv

# Start STT Microservice (auto-downloads small.en on first request)
python services/stt_service/app.py
```

5. Copy the public URL for Pod 3:
   `https://<POD3_ID>-8004.proxy.runpod.net`

---

### Step 4: Configure and Run the API Gateway

The Gateway uses almost no CPU or RAM. You can run it on:
- Pod 1 alongside the LLM.
- A cheap $5/month cloud VPS (e.g., DigitalOcean, Hetzner).
- Free cloud hosting (Render, Railway).

1. In the Gateway host, open the `.env` file and set the URLs you copied from Pods 1, 2, and 3:

```env
# ==============================================================================
# Downstream Microservices on RunPod
# ==============================================================================
LLM_SERVICE_URL=https://<POD1_ID>-8002.proxy.runpod.net
TTS_SERVICE_URL=https://<POD2_ID>-8003.proxy.runpod.net
STT_SERVICE_URL=https://<POD3_ID>-8004.proxy.runpod.net

# Gateway Port and Security
GATEWAY_PORT=8000
API_KEY=tingo-master-key-1234567890abcdef
```

2. Start the Gateway:

```bash
python services/gateway/app.py
```

3. Expose Port `8000`. Your public endpoint for all frontend clients is now:
   `https://<GATEWAY_HOST>-8000.proxy.runpod.net`

---

## Strategy B: Multi-GPU Single Pod (e.g. 2x RTX 3090 Pod)

If you rent **one** RunPod pod with **multiple GPUs** (e.g., `2x RTX 3090` or `4x RTX 4090`), all microservices run inside the same terminal, but each service is pinned to its own dedicated GPU card using the `CUDA_VISIBLE_DEVICES` environment variable.

```text
┌────────────────────────────────────────────────────────┐
│                   Single RunPod Pod                    │
│                                                        │
│  ┌─────────────────────────┐ ┌──────────────────────┐  │
│  │     Physical GPU 0      │ │    Physical GPU 1    │  │
│  │  CUDA_VISIBLE_DEVICES=0 │ │CUDA_VISIBLE_DEVICES=1│  │
│  │   LLM Service (8002)    │ │   STT Service (8004) │  │
│  │                         │ │   TTS Service (8003) │  │
│  └─────────────────────────┘ └──────────────────────┘  │
│                                                        │
│                  Host CPU: Gateway (8000)              │
└────────────────────────────────────────────────────────┘
```

### Steps for Strategy B:

1. Deploy a pod with **2x GPUs** (e.g., 2x RTX 3090) and expose port **8000**.
2. Run the one-click setup script:
   ```bash
   bash runpod_setup.sh
   ```
3. Launch each service with its assigned GPU in background sessions using `tmux` or `nohup`:

```bash
# GPU 0: Dedicated to LLM inference (Mistral / Llama / Qwen)
CUDA_VISIBLE_DEVICES=0 python services/llm_service/app.py > llm.log 2>&1 &

# GPU 1: Shared between Faster-Whisper and Kokoro TTS
CUDA_VISIBLE_DEVICES=1 python services/tts_service/app.py > tts.log 2>&1 &
CUDA_VISIBLE_DEVICES=1 python services/stt_service/app.py > stt.log 2>&1 &

# Host CPU: API Gateway on port 8000
python services/gateway/app.py > gateway.log 2>&1 &
```

---

## Strategy C: Running EACH Model in a Different GPU

If you want to run **3 different LLM models** (e.g. Mistral 7B, Qwen Coder, and Phi-3) each on its own dedicated GPU so they never fight for VRAM:

### Option 1: 1 Pod with 3 or 4 GPUs (e.g., 3x or 4x RTX 3090)
In this setup, our `services/llm_service/engine.py` assigns each model to a dedicated physical GPU index via `llama.cpp`'s native `main_gpu` parameter.

In `.env`, configure the physical GPU ID for each model:
```env
# Physical GPU assignments:
GPU_MISTRAL=0    # Mistral 7B loads into GPU 0
GPU_CODER=1      # Qwen Coder loads into GPU 1
GPU_FAST=2       # Phi-3 Mini loads into GPU 2
```
When a client requests `mistral-7b`, it executes on GPU 0. When another client requests `qwen-coder`, it executes in parallel on GPU 1. Neither model is evicted from VRAM!

### Option 2: 3 Separate RunPod Pods (1 GPU per Pod)
If you rent 3 separate RunPod Pods (each with 1 GPU):
- **Pod 1:** Runs `llm_service` hosting Mistral ➡️ `https://pod1-8002.proxy.runpod.net`
- **Pod 2:** Runs `llm_service` hosting Qwen Coder ➡️ `https://pod2-8002.proxy.runpod.net`
- **Pod 3:** Runs `llm_service` hosting Phi-3 Mini ➡️ `https://pod3-8002.proxy.runpod.net`

In the **API Gateway's `.env`**, add the per-model routes:
```env
MODEL_MISTRAL_URL=https://pod1-8002.proxy.runpod.net
MODEL_CODER_URL=https://pod2-8002.proxy.runpod.net
MODEL_FAST_URL=https://pod3-8002.proxy.runpod.net
```
The Gateway automatically inspects the `"model"` field in the client's request:
- `"model": "mistral-7b"` ➡️ Dispatched directly to Pod 1.
- `"model": "qwen-coder"` ➡️ Dispatched directly to Pod 2.
- `"model": "phi-3-mini"` ➡️ Dispatched directly to Pod 3.

4. Verify GPU memory distribution:
   ```bash
   nvidia-smi
   ```
   You will see:
   - **GPU 0:** ~5 GB VRAM utilized by LLM.
   - **GPU 1:** ~2 GB VRAM utilized by STT + TTS.

---

## Strategy C: RunPod Private VPC Networking (Zero Latency)

When running multiple pods in Strategy A, public proxy URLs travel over the internet. To eliminate internet latency between Pods:

1. When deploying Pods on RunPod, select the **same Data Center** (e.g., `US-NJ-1`).
2. Attach all pods to the same **RunPod Network Volume** or **Private VPC**.
3. Use the Pods' internal private IP addresses (`10.x.x.x`) in the Gateway's `.env`:
   ```env
   LLM_SERVICE_URL=http://10.20.1.4:8002
   TTS_SERVICE_URL=http://10.20.1.5:8003
   STT_SERVICE_URL=http://10.20.1.6:8004
   ```
This provides sub-millisecond local network speeds between your microservices at zero bandwidth cost.

---

## Verification & Testing

Once your services are running (either Strategy A or B), run the automated end-to-end test against your Gateway:

```powershell
# In PowerShell:
powershell -ExecutionPolicy Bypass -File .\test_api.ps1
```

Or test with `curl`:
```bash
# 1. Health check across all remote GPUs:
curl https://<GATEWAY_URL>/health

# 2. Chat completion:
curl -X POST https://<GATEWAY_URL>/v1/chat/completions \
  -H "Authorization: Bearer tingo-master-key-1234567890abcdef" \
  -H "Content-Type: application/json" \
  -d '{"model": "mistral-7b", "messages": [{"role": "user", "content": "Hello from RunPod!"}]}'
```
