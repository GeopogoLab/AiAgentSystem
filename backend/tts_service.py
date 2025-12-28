"""Standalone FastAPI TTS Service - 本地语音合成服务

使用方式:
    python3 tts_service.py

API 端点:
    POST /tts - 文本转语音
    GET /health - 健康检查
    GET /models - 列出可用模型
"""

import asyncio
import base64
import os
import tempfile
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

try:
    from TTS.api import TTS
except ImportError:
    raise ImportError("请先安装 TTS 库: pip install TTS")

# ===== 配置 =====
TTS_MODEL = os.getenv("LOCAL_TTS_MODEL", "tts_models/en/ljspeech/tacotron2-DDC")
TTS_DEVICE = os.getenv("LOCAL_TTS_DEVICE", "cpu")
TTS_FORMAT = os.getenv("LOCAL_TTS_FORMAT", "wav")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8001))

# ===== FastAPI 应用 =====
app = FastAPI(
    title="Local TTS Service",
    description="本地文本转语音服务 - 基于 Coqui TTS",
    version="1.0.0"
)

# 全局 TTS 模型实例
tts_model: Optional[TTS] = None


def get_tts_model() -> TTS:
    """获取或初始化 TTS 模型（延迟加载）"""
    global tts_model
    if tts_model is None:
        print(f"正在加载 TTS 模型: {TTS_MODEL}")
        print(f"设备: {TTS_DEVICE}")

        gpu_flag = TTS_DEVICE.lower().startswith("cuda")
        tts_model = TTS(
            model_name=TTS_MODEL,
            progress_bar=True,
            gpu=gpu_flag,
        )
        print("✅ TTS 模型加载完成")

    return tts_model


# ===== 数据模型 =====

class TTSRequest(BaseModel):
    """TTS 请求"""
    text: str = Field(..., description="要合成的文本", min_length=1, max_length=5000)
    voice: Optional[str] = Field(None, description="说话人（可选）")
    format: Optional[str] = Field("wav", description="音频格式 (wav/mp3)")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "Hello, this is a test of the text to speech service.",
                "voice": None,
                "format": "wav"
            }
        }


class TTSResponse(BaseModel):
    """TTS 响应"""
    audio_base64: str = Field(..., description="Base64 编码的音频数据")
    voice: str = Field(..., description="使用的说话人")
    format: str = Field(..., description="音频格式")
    text: str = Field(..., description="合成的文本")
    duration_sec: float = Field(..., description="音频时长（秒）")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = "ok"
    model: str
    device: str


class ModelsResponse(BaseModel):
    """模型列表响应"""
    current_model: str
    available_models: list[str]


# ===== API 端点 =====

@app.get("/", tags=["Info"])
async def root():
    """服务信息"""
    return {
        "service": "Local TTS Service",
        "version": "1.0.0",
        "model": TTS_MODEL,
        "device": TTS_DEVICE,
        "endpoints": {
            "tts": "POST /tts",
            "health": "GET /health",
            "models": "GET /models"
        }
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "model": TTS_MODEL,
        "device": TTS_DEVICE
    }


@app.get("/models", response_model=ModelsResponse, tags=["Models"])
async def list_models():
    """列出可用的 TTS 模型"""
    # 常用的英文 TTS 模型
    available = [
        "tts_models/en/ljspeech/tacotron2-DDC",
        "tts_models/en/ljspeech/tacotron2-DCA",
        "tts_models/en/ljspeech/glow-tts",
        "tts_models/en/ljspeech/speedy-speech",
        "tts_models/en/ljspeech/neural_hmm",
        "tts_models/en/vctk/vits",
        "tts_models/en/sam/tacotron-DDC",
        "tts_models/multilingual/multi-dataset/xtts_v2",
    ]

    return {
        "current_model": TTS_MODEL,
        "available_models": available
    }


@app.post("/tts", response_model=TTSResponse, tags=["TTS"])
async def text_to_speech(request: TTSRequest):
    """
    文本转语音 API

    将输入的文本转换为语音，返回 Base64 编码的音频数据。

    参数:
    - text: 要合成的文本（1-5000 字符）
    - voice: 说话人（可选，部分模型支持）
    - format: 音频格式（默认 wav）

    返回:
    - audio_base64: Base64 编码的音频
    - voice: 使用的说话人
    - format: 音频格式
    - text: 原始文本
    - duration_sec: 音频时长
    """
    try:
        # 获取 TTS 模型
        model = get_tts_model()

        # 运行 TTS（在线程池中执行，避免阻塞）
        loop = asyncio.get_running_loop()

        def _synthesize() -> tuple[bytes, float]:
            """在后台线程中合成语音"""
            # 创建临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{request.format}") as tmp_file:
                tmp_path = tmp_file.name

            try:
                # 合成语音
                model.tts_to_file(
                    text=request.text,
                    speaker=request.voice or None,
                    file_path=tmp_path,
                )

                # 读取音频数据
                with open(tmp_path, "rb") as f:
                    audio_bytes = f.read()

                # 估算时长（基于文件大小，粗略估计）
                # WAV: 大约 44100 Hz * 2 bytes/sample = 88200 bytes/sec
                duration = len(audio_bytes) / 88200.0 if request.format == "wav" else 0.0

                return audio_bytes, duration

            finally:
                # 清理临时文件
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

        # 在线程池中执行合成（避免阻塞事件循环）
        audio_bytes, duration = await loop.run_in_executor(None, _synthesize)

        # Base64 编码
        audio_base64 = base64.b64encode(audio_bytes).decode("ascii")

        return TTSResponse(
            audio_base64=audio_base64,
            voice=request.voice or "default",
            format=request.format,
            text=request.text,
            duration_sec=duration
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"TTS 合成失败: {str(e)}"
        )


# ===== 启动服务 =====

if __name__ == "__main__":
    print("=" * 60)
    print("🎙️  本地 TTS 服务启动中...")
    print("=" * 60)
    print(f"模型: {TTS_MODEL}")
    print(f"设备: {TTS_DEVICE}")
    print(f"地址: http://{HOST}:{PORT}")
    print(f"文档: http://{HOST}:{PORT}/docs")
    print("=" * 60)

    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info"
    )
