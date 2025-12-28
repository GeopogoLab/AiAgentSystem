"""Local TTS helper for offline speech synthesis."""
from __future__ import annotations

import asyncio
import base64
import os
import tempfile
from typing import Optional

from fastapi import HTTPException

try:
    from TTS.api import TTS
except ImportError:  # pragma: no cover
    TTS = None

from backend.config import config
from backend.models import TTSResponse

_local_tts_model: Optional[TTS] = None


def _ensure_model() -> TTS:
    global _local_tts_model
    if _local_tts_model:
        return _local_tts_model
    if TTS is None:
        raise HTTPException(
            status_code=500,
            detail="Local TTS dependency missing, install `TTS` to enable offline voices",
        )
    gpu_flag = config.LOCAL_TTS_DEVICE.lower().startswith("cuda")
    try:
        _local_tts_model = TTS(
            model_name=config.LOCAL_TTS_MODEL,
            progress_bar=False,
            gpu=gpu_flag,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load local TTS model '{config.LOCAL_TTS_MODEL}': {exc}",
        )
    return _local_tts_model


async def synthesize_local_tts(text: str, voice: Optional[str] = None) -> TTSResponse:
    """Synthesize speech with a locally hosted model and return base64 audio."""
    if not text:
        raise HTTPException(status_code=400, detail="Missing text for local TTS")

    model = _ensure_model()
    speaker = voice or config.LOCAL_TTS_SPEAKER or None
    loop = asyncio.get_running_loop()

    def _render() -> bytes:
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        tmp_path = tmp_file.name
        tmp_file.close()
        try:
            model.tts_to_file(text=text, speaker=speaker, file_path=tmp_path)
            with open(tmp_path, "rb") as fp:
                return fp.read()
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    try:
        audio_bytes = await loop.run_in_executor(None, _render)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Local TTS synthesis failed: {exc}")

    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
    return TTSResponse(
        audio_base64=audio_b64,
        voice=speaker or "local",
        format=config.LOCAL_TTS_FORMAT or "wav",
    )
