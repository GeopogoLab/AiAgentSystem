# Voice service hub

This workspace now owns the core STT/TTS helpers that drive the FastAPI backend. They live under `voice_service/` and are imported through the root-level `voice_service` package so the rest of the codebase can stay untouched.

## Directory layout

- `voice_service/local_tts.py` – Local Coqui/TTS helper used by the `/tts` HTTP endpoint and streaming service. It pulls configuration from `backend.config`.
- `voice_service/streaming_tts.py` – Piper + FFmpeg streaming TTS engine consumed by `/ws/tts`.
- `voice_service/stt/backends.py` – `STTBackendRouter` that builds AssemblyAI/Whisper fallback targets.

## Operations checklist

1. **Dependencies**
   - Ensure `piper`, `ffmpeg`, and `TTS` are installed when running the local TTS pathway.
2. **Launching**
   - The files here are automatically available once you run `uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000`.
   - There is no separate process for them; they are shared helpers imported by the backend.
3. **Testing**
   - Use `test_local_tts.py` and `test_streaming_tts_playback.py` (on the repo root) to verify the workspace-managed modules in isolation.
4. **Management**
   - Treat this workspace as the single source for voice logic. When making changes to Piper, local TTS, or STT routing, update the files here and update the docs in this folder so deployments always reference the workspace.
