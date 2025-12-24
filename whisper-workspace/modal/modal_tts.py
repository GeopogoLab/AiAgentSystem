"""Modal Coqui XTTS-v2 TTS Service - 完全本地的语音合成服务

部署 XTTS-v2 模型作为本地 TTS 方案
- GPU 推理: XTTS-v2 (A10G/T4)
- REST API: FastAPI (CPU, always-on)
- 多语言支持: 英语、中文等 17 种语言
- 声音克隆: 支持提供参考音频
"""

import modal
import base64
import io
from typing import Optional

# ===== 配置 =====
APP_NAME = "coqui-xtts-tts"
GPU_TYPE = "T4"  # T4 ($0.24/h) 对 XTTS 足够，A10G 会更快但贵
SCALEDOWN_WINDOW = 300  # 5 分钟无请求后释放 GPU

app = modal.App(APP_NAME)

# ===== 镜像定义 =====

# 1. XTTS 推理镜像 (GPU)
xtts_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "ffmpeg")  # XTTS 需要 ffmpeg
    .pip_install(
        "TTS==0.22.0",  # Coqui TTS 库
        "torch==2.1.0",
        "torchaudio==2.1.0",
        "numpy==1.24.3",
        "scipy",
    )
)

# 2. API Wrapper 镜像 (CPU, 轻量)
wrapper_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastapi[standard]==0.115.4",
        "numpy==1.24.3",
    )
)

# ===== GPU 推理函数 =====

xtts_model = None  # 全局模型缓存


@app.function(
    image=xtts_image,
    gpu=GPU_TYPE,
    min_containers=0,  # 成本优化：按需启动
    scaledown_window=SCALEDOWN_WINDOW,
    timeout=300,  # TTS 可能需要更长时间
)
def synthesize_speech(
    text: str,
    language: str = "en",
    speaker_wav_b64: Optional[str] = None,
) -> bytes:
    """
    XTTS-v2 语音合成

    Args:
        text: 要合成的文本
        language: 语言代码 (en, zh-cn, ja, etc.)
        speaker_wav_b64: 可选的参考音频 (Base64 编码的 WAV)，用于声音克隆

    Returns:
        合成的音频数据 (WAV 格式, 24kHz, 16-bit)
    """
    global xtts_model

    # 延迟加载模型
    if xtts_model is None:
        import torch
        from TTS.api import TTS

        print(f"加载 XTTS-v2 模型...")
        print(f"CUDA 可用: {torch.cuda.is_available()}")

        # 加载 XTTS-v2 模型
        xtts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2")

        if torch.cuda.is_available():
            xtts_model = xtts_model.to("cuda")

        print("✅ XTTS-v2 模型加载完成")

    import tempfile
    import wave
    import numpy as np

    print(f"开始合成: 文本长度={len(text)}, 语言={language}")

    # 如果提供了参考音频，使用声音克隆
    speaker_wav_path = None
    if speaker_wav_b64:
        # 解码参考音频
        speaker_wav_bytes = base64.b64decode(speaker_wav_b64)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
            f.write(speaker_wav_bytes)
            speaker_wav_path = f.name
        print(f"使用声音克隆，参考音频: {len(speaker_wav_bytes)} bytes")

    # 合成音频
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as output_file:
        output_path = output_file.name

    try:
        # XTTS API
        if speaker_wav_path:
            # 声音克隆模式
            xtts_model.tts_to_file(
                text=text,
                speaker_wav=speaker_wav_path,
                language=language,
                file_path=output_path,
            )
        else:
            # 使用默认说话人
            xtts_model.tts_to_file(
                text=text,
                language=language,
                file_path=output_path,
            )

        # 读取合成的音频
        with open(output_path, 'rb') as f:
            audio_data = f.read()

        print(f"✅ 合成完成: {len(audio_data)} bytes")
        return audio_data

    finally:
        # 清理临时文件
        import os
        if speaker_wav_path and os.path.exists(speaker_wav_path):
            os.remove(speaker_wav_path)
        if os.path.exists(output_path):
            os.remove(output_path)


# ===== FastAPI REST 服务器 =====

@app.function(image=wrapper_image)
@modal.asgi_app()
def wrapper():
    """永远在线的 REST API 服务器"""
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    from typing import Optional

    api = FastAPI(title="Coqui XTTS-v2 TTS Service")

    class TTSRequest(BaseModel):
        text: str
        language: str = "en"  # en, zh-cn, ja, de, fr, es, it, pt, pl, tr, ru, nl, cs, ar, zh-tw, hu, ko
        speaker_wav_b64: Optional[str] = None  # Base64 编码的参考音频

    class TTSResponse(BaseModel):
        audio_b64: str  # Base64 编码的 WAV 音频
        sample_rate: int = 24000
        text: str
        language: str

    @api.get("/health")
    async def health():
        return {"status": "ok", "service": "xtts-tts"}

    @api.post("/tts", response_model=TTSResponse)
    async def text_to_speech(request: TTSRequest):
        """
        文本转语音 API

        示例请求:
        ```json
        {
            "text": "Hello, this is a test of the XTTS voice synthesis system.",
            "language": "en"
        }
        ```

        支持的语言:
        - en (English)
        - zh-cn (Chinese Simplified)
        - ja (Japanese)
        - de (German)
        - fr (French)
        - es (Spanish)
        - it (Italian)
        - pt (Portuguese)
        - pl (Polish)
        - tr (Turkish)
        - ru (Russian)
        - nl (Dutch)
        - cs (Czech)
        - ar (Arabic)
        - zh-tw (Chinese Traditional)
        - hu (Hungarian)
        - ko (Korean)
        """
        try:
            # 验证文本长度
            if len(request.text) > 5000:
                raise HTTPException(status_code=400, detail="文本过长 (最多 5000 字符)")

            if not request.text.strip():
                raise HTTPException(status_code=400, detail="文本不能为空")

            # 调用 GPU 推理函数
            audio_bytes = synthesize_speech.remote(
                text=request.text,
                language=request.language,
                speaker_wav_b64=request.speaker_wav_b64,
            )

            # Base64 编码音频
            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

            return TTSResponse(
                audio_b64=audio_b64,
                sample_rate=24000,
                text=request.text,
                language=request.language,
            )

        except Exception as e:
            print(f"❌ TTS 错误: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @api.get("/languages")
    async def list_languages():
        """列出支持的语言"""
        return {
            "languages": {
                "en": "English",
                "zh-cn": "Chinese (Simplified)",
                "ja": "Japanese",
                "de": "German",
                "fr": "French",
                "es": "Spanish",
                "it": "Italian",
                "pt": "Portuguese",
                "pl": "Polish",
                "tr": "Turkish",
                "ru": "Russian",
                "nl": "Dutch",
                "cs": "Czech",
                "ar": "Arabic",
                "zh-tw": "Chinese (Traditional)",
                "hu": "Hungarian",
                "ko": "Korean",
            }
        }

    return api


# ===== 本地测试入口 =====

@app.local_entrypoint()
def main():
    """本地测试"""
    print(f"XTTS-v2 TTS 服务配置:")
    print(f"  模型: XTTS-v2 (multilingual)")
    print(f"  GPU: {GPU_TYPE}")
    print(f"  空闲超时: {SCALEDOWN_WINDOW}秒")
    print(f"  支持语言: 17 种")
    print(f"\n使用 'modal serve modal_tts.py' 启动服务进行测试")
