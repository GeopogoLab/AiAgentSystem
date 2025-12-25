# 🧋 Tea Order Agent System

A voice-first tea-order assistant that combines speech recognition, multi-model LLM routing, and realtime production visibility. It keeps conversations in context, validates order data, and updates both the frontend queue board and SQLite-backed backend with every confirmed order.

## ✨ Core Capabilities

- 🎤 **Automatic STT** via AssemblyAI WebSocket streaming with a Whisper fallback when AssemblyAI is unavailable.
- 🗣️ **Multi-model routing**: OpenRouter (Llama-3.3-70B) is the primary model, Modal vLLM 70B acts as the standby, and stricter rules ensure the agent never replies before tools finish.
- 🛠️ **Function Calling**: Tools expose order lookup, progress queries, and queue snapshots, letting the agent answer with real-time data.
- 🧠 **Session awareness**: Conversation history persists with order drafts and production status, enabling follow-up questions like “Is order #5 ready?” without repeated context.
- 📊 **Both customer and backstage views**: A React front-end for customers and a Tailwind+shadcn queue board for staff show production updates side-by-side.
- 🧾 **Reliable persistence**: SQLite stores every order with structured fields for drink, cup, sweetness, ice, add-ons, and status.

## 🏗️ Architecture Overview

```
┌────────────────────────────┐
│  React + Tailwind Frontends │
└─────────────┬──────────────┘
              │
              ↓
┌────────────────────────────┐
│     FastAPI Backend         │
├────────────────────────────┤
│  AssemblyAI (STT + TTS)     │
│  OpenRouter → vLLM → Rules  │
│  Function Calling Tools     │
│  SQLite Order Store         │
└────────────────────────────┘
```

LLM requests always flow from OpenRouter to vLLM; if both fail, the agent falls back to synchronous rule-based replies so users never hit a hard stop.

## 📋 Core Flows

### Order Intake
1. User speaks or types a request.
2. AssemblyAI transcribes in real time; if it fails, Whisper kicks in.
3. The LLM agent collects structured order details through function calls.
4. The backend validates, confirms, and saves the order.
5. Frontend mirrors stage updates and prices each order.

### Progress Check (Function Calling)
1. User asks about an existing order.
2. Agent triggers `get_order_status` or production queue APIs.
3. Backend returns production status, beverage, sweetness, ice, and add-ons.
4. Agent responds in natural language with live queue context.

## 🚀 Quick Start

### 1. Requirements
- Python 3.8+
- Node.js 16+ (pnpm/yarn/npm ok)
- Modal CLI (optional for deployment)

### 2. Install
```bash
# Backend
pip install -r requirements.txt

# Frontend
cd frontend
pnpm install   # or npm/yarn
```

### 3. Configure
Copy `.env.example` to `.env` and fill the keys, including:
- `ASSEMBLYAI_API_KEY`, streaming params, and `ASSEMBLYAI_TTS_VOICE`.
- `OPENROUTER_API_KEY` (primary) plus `OPENAI_API_KEY` for compatibility.
- `VLLM_BASE_URL`/`VLLM_API_KEY` for the Modal or Linux fallback.
- Whisper endpoint and API key for Offline STT.

### 4. Run
```bash
# Backend
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (new terminal)
cd frontend
pnpm dev
```
```
Frontend: http://localhost:3000  |  API docs: http://localhost:8000/docs

## 📦 Deployment Notes
- Use `deploy.sh` for one-command Modal deployment and see `MODAL_DEPLOYMENT.md` for the full process.
- There is also a Linux-oriented `vllm-workspace/linux-deployment/` package with Docker Compose, scripts, and monitoring helpers for larger teams.
- Any Tailwind+shadcn UI change must build via Vite before shipping (per the architecture rules).

## 🧪 Testing
- Backend: `python -m pytest` or the existing helpers under `test_api.py` / `test_websocket.html`.
- Frontend: `pnpm test` (if configured) or `pnpm run build` to ensure Tailwind/shadcn compiles.

## 🛠️ vLLM Fallback
- Deploy `vllm-workspace/modal/modal_vllm.py` or the Linux scripts in `vllm-workspace/linux-deployment/`.
- After deployment, copy the returned URL into `.env` as `VLLM_BASE_URL` and define `VLLM_API_KEY` if Modal security is enabled.
- vLLM serves as the second route for every prompt; failures are logged and trigger fallback metrics tracking.

## 🎙️ Local English TTS
- Install the local speech synthesis stack (Coqui TTS) via `pip install TTS` so you can run TTS on your 32 GB GPU without calling a hosted service.
- Configure the backend by setting `TTS_PROVIDER=local`, `LOCAL_TTS_MODEL=tts_models/en/ljspeech/tacotron2-DDC`, `LOCAL_TTS_DEVICE=cuda`, and `LOCAL_TTS_FORMAT=wav` in `.env`.
- The helper writes the generated waveform to a temporary WAV file, base64 encodes it, and returns `audio_base64`/`audio/wav` so the browser can play the clip without needing AssemblyAI credits.
- Use `LOCAL_TTS_DEVICE=cpu` for lightweight testing, but keep `LOCAL_TTS_MODEL` as an English-only voice to match your requirement.
