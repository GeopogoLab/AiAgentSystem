# STT & TTS 流式传输对比

## 当前状态

| 功能 | 协议 | 是否流式 | 延迟 | 说明 |
|------|------|---------|------|------|
| **STT** 🎤 | WebSocket | ✅ 是 | 低 (~100ms) | 实时发送音频 → 实时返回文字 |
| **TTS** 🔊 | HTTP POST | ❌ 否 | 高 (~2-5s) | 发送文本 → 等待完整音频 → 播放 |

---

## 详细分析

### 1. STT (语音转文字) - 已支持流式 ✅

**工作原理**:
```
用户说话 ──► 浏览器录音 ──► WebSocket 发送音频块
                           │
                           ▼
                      后端 STT 识别
                           │
                           ▼
         部分结果 ◄──── partial_transcript
         最终结果 ◄──── final_transcript
```

**优势**:
- ✅ 边说边识别，无需等待
- ✅ 实时反馈（partial results）
- ✅ 低延迟（~100-300ms）

**实现位置**:
- 前端: `VoiceInput.tsx` (WebSocket 客户端)
- 后端: `backend/main.py` - `/ws/stt`

---

### 2. TTS (文字转语音) - 当前非流式 ❌

**当前工作原理**:
```
文本 ──► HTTP POST /tts ──► 后端完整合成 ──► 返回 Base64
                                              │
                                              ▼
                                    前端解码 → 播放
```

**问题**:
- ❌ 需要等待完整音频生成（2-5 秒）
- ❌ 长文本延迟更高
- ❌ 用户体验不够流畅

**改进空间**: 可以改造为流式！

---

## 流式 TTS 设计方案

### 方案 1: WebSocket 流式 TTS (推荐)

**工作原理**:
```
文本 ──► WebSocket /ws/tts ──► 后端边合成边发送音频块
                                │
                                ▼
                        chunk 1 (0.5s audio)
                        chunk 2 (0.5s audio)
                        chunk 3 (0.5s audio)
                                │
                                ▼
                        前端边接收边播放
```

**优势**:
- ✅ 首字节延迟低 (TTFB ~200ms)
- ✅ 边合成边播放，总延迟降低 50%+
- ✅ 适合长文本
- ✅ 与 STT WebSocket 架构一致

**实现要点**:
```python
@app.websocket("/ws/tts")
async def streaming_tts(websocket: WebSocket):
    await websocket.accept()

    # 接收文本
    data = await websocket.receive_json()
    text = data['text']

    # 流式合成（需要支持流式的 TTS 引擎）
    async for audio_chunk in tts_engine.synthesize_streaming(text):
        await websocket.send_bytes(audio_chunk)

    await websocket.close()
```

**前端实现**:
```typescript
const ws = new WebSocket('ws://localhost:8000/ws/tts');
const mediaSource = new MediaSource();
const audio = new Audio(URL.createObjectURL(mediaSource));

ws.onmessage = (event) => {
  const chunk = event.data; // ArrayBuffer
  appendToMediaSource(chunk); // 追加到播放缓冲区
};
```

---

### 方案 2: HTTP 流式响应 (Server-Sent Events)

**工作原理**:
```python
from fastapi.responses import StreamingResponse

@app.post("/tts/stream")
async def streaming_tts(request: TTSRequest):
    async def generate():
        async for chunk in tts_engine.synthesize_streaming(request.text):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="audio/wav",
        headers={"Cache-Control": "no-cache"}
    )
```

**前端**:
```typescript
const response = await fetch('/tts/stream', {
  method: 'POST',
  body: JSON.stringify({text: "Hello"})
});

const reader = response.body.getReader();
const chunks = [];

while (true) {
  const {done, value} = await reader.read();
  if (done) break;
  chunks.push(value);
  // 边接收边播放
}
```

---

### 方案 3: 分块合成 + HTTP (简单但效果有限)

**工作原理**:
```
长文本 → 分割成句子 → 并发请求多个 TTS
       → 按顺序播放
```

**优势**:
- ✅ 无需改造协议
- ✅ 实现简单

**劣势**:
- ❌ 仍有等待时间
- ❌ 不是真正的流式

---

## 支持流式的 TTS 引擎

| TTS 引擎 | 流式支持 | 质量 | 延迟 |
|---------|---------|------|------|
| Coqui TTS | ❌ 不支持 | 高 | 高 |
| XTTS-v2 | ❌ 不支持 | 极高 | 极高 |
| AssemblyAI | ❌ 不支持 | 高 | 中 |
| OpenAI TTS | ✅ 支持 | 极高 | 低 |
| ElevenLabs | ✅ 支持 | 极高 | 极低 |
| Azure TTS | ✅ 部分支持 | 高 | 低 |
| Google TTS | ❌ 不支持 | 中 | 中 |

**注意**: Coqui TTS (你当前使用的) **不支持流式合成**，需要等待完整音频生成。

---

## 推荐方案

### 短期方案（无需修改 TTS 引擎）

**使用 OpenAI TTS API** (支持流式):

```python
from openai import AsyncOpenAI

@app.websocket("/ws/tts")
async def streaming_tts_openai(websocket: WebSocket):
    await websocket.accept()
    data = await websocket.receive_json()

    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async with client.audio.speech.with_streaming_response.create(
        model="tts-1",
        voice="alloy",
        input=data['text'],
        response_format="opus"  # 低延迟格式
    ) as response:
        async for chunk in response.iter_bytes(chunk_size=4096):
            await websocket.send_bytes(chunk)

    await websocket.close()
```

**成本**: ~$0.015 / 1000 字符（非常便宜）

**延迟**: 首字节 ~200ms，比 Coqui TTS 快 10 倍

---

### 长期方案（本地流式 TTS）

使用支持流式的本地 TTS:

1. **Piper TTS** (fast, streaming-capable)
   - 基于 VITS 模型
   - 支持流式输出
   - CPU 友好

2. **StyleTTS2** (high quality)
   - 质量接近 XTTS
   - 可以实现伪流式（分句合成）

3. **Custom VITS**
   - 修改 VITS 模型支持流式

---

## 对比总结

| 方案 | 流式 STT | 流式 TTS | 总延迟 | 实现难度 |
|------|---------|---------|--------|---------|
| **当前** | ✅ | ❌ | 3-6s | - |
| **OpenAI TTS** | ✅ | ✅ | 0.5-1s | 低 |
| **Piper TTS** | ✅ | ✅ | 1-2s | 中 |
| **分块 Coqui** | ✅ | 🟡 | 2-3s | 低 |

---

## 下一步行动

### 选项 1: 快速验证 - 使用 OpenAI TTS (推荐)
- 添加 WebSocket `/ws/tts` 端点
- 集成 OpenAI Streaming API
- 前端改用 WebSocket 接收音频

### 选项 2: 保持本地 - 分块优化
- 将长文本分句
- 并发请求多个 TTS
- 顺序播放

### 选项 3: 混合方案
- STT: 保持当前 (WebSocket)
- TTS: 短文本用本地，长文本用 OpenAI 流式

需要我帮你实现哪个方案？
