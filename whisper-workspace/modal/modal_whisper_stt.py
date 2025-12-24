"""Modal Whisper STT Service - 备用语音识别服务

部署 Whisper Medium 模型作为 AssemblyAI 的降级方案
- GPU 推理: faster-whisper (A10G)
- WebSocket 服务: FastAPI (CPU, always-on)
- VAD 分段: webrtcvad
"""

import modal
import base64
import json
import struct
import numpy as np
from typing import Optional

# ===== 配置 =====
WHISPER_MODEL = "medium"  # 平衡准确性和速度
GPU_TYPE = "A10G"         # $0.6/h, whisper-medium 足够
SCALEDOWN_WINDOW = 180    # 3 分钟无请求后释放 GPU
APP_NAME = "whisper-stt"

app = modal.App(APP_NAME)

# ===== 镜像定义 =====

# 1. Whisper 推理镜像 (GPU) - 使用官方 OpenAI Whisper
whisper_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")  # OpenAI Whisper 需要 ffmpeg
    .pip_install(
        "openai-whisper==20231117",  # 官方实现，更稳定
        "numpy==1.24.3",
    )
)

# 2. Wrapper 镜像 (CPU, 轻量) - FastAPI + VAD
wrapper_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastapi[standard]==0.115.4",
        "webrtcvad==2.0.10",
        "numpy==1.24.3",
    )
)

# ===== GPU 推理函数 =====

whisper_model = None  # 全局模型缓存


@app.function(
    image=whisper_image,
    gpu=GPU_TYPE,
    min_containers=0,  # 成本优化：按需启动
    scaledown_window=SCALEDOWN_WINDOW,
)
def transcribe_audio(audio_bytes: bytes, sample_rate: int = 16000) -> dict:
    """Whisper 音频转录（OpenAI Whisper 官方实现）

    Args:
        audio_bytes: PCM 16-bit 音频数据
        sample_rate: 采样率（默认 16kHz）

    Returns:
        {"text": str, "language": str, "language_probability": float}
    """
    global whisper_model

    # 延迟加载模型（仅在 GPU 容器中）
    if whisper_model is None:
        import whisper
        import torch

        print(f"加载 Whisper {WHISPER_MODEL} 模型...")
        print(f"CUDA 可用: {torch.cuda.is_available()}")

        whisper_model = whisper.load_model(
            WHISPER_MODEL,
            device="cuda" if torch.cuda.is_available() else "cpu"
        )
        print("✅ 模型加载完成")

    # PCM bytes → numpy float32 array
    audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
    audio_float32 = audio_int16.astype(np.float32) / 32768.0  # 归一化到 [-1, 1]

    # Inference
    print(f"开始转录: {len(audio_float32)} 样本")
    result = whisper_model.transcribe(
        audio_float32,
        language="en",  # English
        fp16=True,  # 使用 FP16 加速
    )

    return {
        "text": result["text"].strip(),
        "language": result.get("language", "en"),
        "language_probability": 1.0,  # OpenAI Whisper 不提供此字段
    }


# ===== FastAPI WebSocket 服务器 =====

@app.function(image=wrapper_image)
@modal.asgi_app()
def wrapper():
    """永远在线的 WebSocket 服务器 + VAD 分段"""
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    import webrtcvad

    api = FastAPI(title="Whisper STT Service")

    # VAD 配置
    VAD_AGGRESSIVENESS = 2  # 0-3, 2 = 中等敏感度
    FRAME_DURATION_MS = 30  # 每帧 30ms
    SAMPLE_RATE = 16000
    BYTES_PER_FRAME = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000) * 2  # 16-bit = 2 bytes/sample

    # 分段配置
    MIN_SEGMENT_DURATION_SEC = 1.0  # 最小段长 1 秒
    MAX_SEGMENT_DURATION_SEC = 5.0  # 最大段长 5 秒
    SILENCE_THRESHOLD_FRAMES = 30   # 静音 30 帧（~1 秒）后分段

    @api.get("/health")
    async def health():
        return {"status": "ok", "service": "whisper-stt"}

    @api.websocket("/ws/stt")
    async def websocket_stt(websocket: WebSocket):
        """WebSocket STT 端点（兼容前端格式）"""
        await websocket.accept()

        vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
        incoming_buffer = bytearray()  # 接收数据缓冲区
        audio_segment = bytearray()    # 累积的音频段
        silence_frames = 0
        speech_frames = 0

        try:
            while True:
                # 接收音频数据（Base64 编码的 PCM）
                message = await websocket.receive_text()
                data = json.loads(message)

                if "audio_data" not in data:
                    continue

                # 解码 Base64 音频
                audio_chunk = base64.b64decode(data["audio_data"])
                incoming_buffer.extend(audio_chunk)

                # VAD 检测（每 30ms 一帧）
                while len(incoming_buffer) >= BYTES_PER_FRAME:
                    frame = bytes(incoming_buffer[:BYTES_PER_FRAME])
                    incoming_buffer = incoming_buffer[BYTES_PER_FRAME:]

                    # 将帧添加到音频段
                    audio_segment.extend(frame)

                    # VAD 判断是否有语音
                    is_speech = vad.is_speech(frame, SAMPLE_RATE)

                    if is_speech:
                        speech_frames += 1
                        silence_frames = 0
                    else:
                        silence_frames += 1

                    # 分段条件
                    segment_duration = len(audio_segment) / (SAMPLE_RATE * 2)  # 秒
                    should_segment = False

                    if speech_frames > 0:
                        # 条件 1: 静音 1 秒后分段
                        if silence_frames >= SILENCE_THRESHOLD_FRAMES:
                            should_segment = True
                        # 条件 2: 超过最大长度强制分段
                        elif segment_duration >= MAX_SEGMENT_DURATION_SEC:
                            should_segment = True

                    if should_segment and segment_duration >= MIN_SEGMENT_DURATION_SEC:
                        # 调用 GPU 推理
                        audio_data = bytes(audio_segment)
                        if len(audio_data) > 0:
                            print(f"处理音频段: {len(audio_data)} bytes, {segment_duration:.1f}秒")

                            # 远程调用 GPU 函数
                            result = transcribe_audio.remote(audio_data, SAMPLE_RATE)

                            # 返回识别结果（兼容 AssemblyAI 格式）
                            if result["text"]:
                                await websocket.send_json({
                                    "message_type": "final_transcript",
                                    "text": result["text"],
                                    "language": result.get("language", "en"),
                                    "confidence": result.get("language_probability", 1.0),
                                })
                                print(f"✅ 识别完成: {result['text']}")

                        # 重置音频段缓冲区
                        audio_segment.clear()
                        speech_frames = 0
                        silence_frames = 0

        except WebSocketDisconnect:
            print("WebSocket 连接断开")
        except Exception as exc:
            print(f"❌ WebSocket 错误: {exc}")
            await websocket.close()

    return api


# ===== 本地测试入口 =====

@app.local_entrypoint()
def main():
    """本地测试"""
    print(f"Whisper STT 服务配置:")
    print(f"  模型: {WHISPER_MODEL}")
    print(f"  GPU: {GPU_TYPE}")
    print(f"  空闲超时: {SCALEDOWN_WINDOW}秒")
    print(f"\n使用 'modal serve' 启动服务进行测试")
