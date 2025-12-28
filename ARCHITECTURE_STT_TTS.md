# STT & TTS 架构说明

## 当前架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                     前端 (React)                             │
│  ┌──────────────────┐              ┌─────────────────────┐  │
│  │  VoiceInput.tsx  │              │    App.tsx          │  │
│  │  (STT 客户端)    │              │   (TTS 客户端)      │  │
│  │                  │              │                     │  │
│  │  • 录音麦克风     │              │  • 播放音频         │  │
│  │  • WebSocket     │              │  • Auto TTS        │  │
│  └──────┬───────────┘              └─────────┬───────────┘  │
│         │                                    │              │
└─────────┼────────────────────────────────────┼──────────────┘
          │ WebSocket                          │ HTTP POST
          │ /ws/stt                            │ /tts
          ▼                                    ▼
┌─────────────────────────────────────────────────────────────┐
│                   后端 (FastAPI - Port 8000)                 │
│  ┌──────────────────┐              ┌─────────────────────┐  │
│  │   STT 端点       │              │    TTS 端点         │  │
│  │  /ws/stt         │              │    /tts             │  │
│  │                  │              │                     │  │
│  │  主: AssemblyAI  │              │  Provider: local    │  │
│  │  备: Whisper     │              │  Provider: gtts     │  │
│  └──────┬───────────┘              │  Provider: assemblyai│ │
│         │                          └─────────┬───────────┘  │
└─────────┼────────────────────────────────────┼──────────────┘
          │                                    │
          ▼                                    ▼
┌─────────────────────┐              ┌─────────────────────┐
│  AssemblyAI API     │              │  本地 TTS           │
│  (云端 STT)         │              │  (whisper-workspace/voice_service/local_tts.py)│
│                     │              │                     │
│  失败时降级 ↓        │              │  Coqui TTS 库      │
│                     │              └─────────────────────┘
│  Whisper STT        │
│  (Modal 部署)       │
└─────────────────────┘
```

## 详细说明

### 1. STT (Speech-to-Text) - 语音转文字

**前端客户端**: `frontend/src/components/VoiceInput.tsx`
- 使用浏览器 MediaRecorder API 录音
- 通过 WebSocket 连接到后端 `/ws/stt`
- 实时发送音频流（PCM 16-bit, 16kHz）
- 接收识别结果（partial 和 final transcript）

**后端服务**: `backend/main.py` - `/ws/stt` (Port 8000)
- **主后端**: AssemblyAI Streaming API (云端)
- **备用后端**: Whisper STT (Modal 部署)
- 自动降级机制（AssemblyAI 失败时切换到 Whisper）
- 配置文件: `whisper-workspace/voice_service/stt/backends.py`

**工作流程**:
```
用户说话 → 浏览器录音 → WebSocket 发送音频
         → 后端 STT 识别 → 返回文字
         → LLM 处理 → 返回回复（可选实时模式）
```

---

### 2. TTS (Text-to-Speech) - 文字转语音

**前端客户端**: `frontend/src/App.tsx`
- 监听最新的 assistant 消息
- 调用 `ApiService.requestTTS(text)` 请求音频
- 接收 Base64 编码的音频或音频 URL
- 使用 HTML5 Audio 播放

**后端服务**: `backend/main.py` - `/tts` (Port 8000)
- **Provider 配置**: `TTS_PROVIDER` 环境变量
  - `local`: 本地 Coqui TTS (`whisper-workspace/voice_service/local_tts.py`)
  - `gtts`: Google TTS (在线，免费)
  - `assemblyai`: AssemblyAI TTS (云端，需 API key)

**工作流程**:
```
LLM 回复 → 前端调用 /tts API → 后端 TTS 合成
        → 返回 Base64 音频 → 前端播放
```

---

### 3. 独立 TTS 服务 (新部署)

**服务文件**: `tts_service.py` (Port 8002)
- 独立的 FastAPI 服务
- 仅提供 TTS 功能
- 不依赖主后端

**端点**:
- `GET /health` - 健康检查
- `GET /models` - 列出可用模型
- `POST /tts` - 文本转语音

**状态**: ✅ 已部署运行在 `http://localhost:8002`

---

## 问题回答

### ❓ STT 和 TTS 是在一个客户端吗？

**是的，在同一个前端客户端**，但使用不同的组件：

| 功能 | 前端组件 | 后端端点 | 协议 | 集成方式 |
|------|---------|---------|------|---------|
| **STT** | `VoiceInput.tsx` | `/ws/stt` | WebSocket | 实时音频流 |
| **TTS** | `App.tsx` | `/tts` | HTTP POST | 请求-响应 |

### 特点：

1. **STT (语音输入)**:
   - 用户点击麦克风按钮
   - 实时识别语音
   - WebSocket 保持连接
   - 支持部分识别结果

2. **TTS (语音播放)**:
   - 自动触发（当 `VITE_ENABLE_AUTO_TTS=true`）
   - 每次 assistant 回复后自动播放
   - HTTP 请求获取音频
   - 使用浏览器播放

3. **独立部署**:
   - 可以将 `tts_service.py` 作为独立服务
   - 不影响主应用
   - 便于水平扩展

---

## 配置文件

### 主后端配置 (`.env`)
```bash
# STT 配置
ASSEMBLYAI_API_KEY=xxx
WHISPER_ENABLED=true
WHISPER_SERVICE_URL=wss://...

# TTS 配置
TTS_PROVIDER=local              # local / gtts / assemblyai
LOCAL_TTS_MODEL=tts_models/en/ljspeech/tacotron2-DDC
LOCAL_TTS_DEVICE=cpu            # cpu / cuda
```

### 前端配置
```bash
VITE_API_URL=http://localhost:8000
VITE_ENABLE_AUTO_TTS=true       # 自动播放 TTS
```

---

## 架构优势

✅ **STT**:
- 实时流式识别
- 自动降级保障
- 支持多种后端

✅ **TTS**:
- 多 Provider 支持
- 本地离线运行
- 可独立部署

✅ **前端**:
- 统一用户体验
- 组件化设计
- 易于维护

---

## 下一步优化建议

1. **统一 TTS 服务**
   - 将主后端的 `/tts` 改为调用独立 TTS 服务 (Port 8002)
   - 解耦 TTS 和主业务逻辑

2. **添加 TTS 缓存**
   - 缓存常用语音片段
   - 减少重复合成

3. **支持多语言**
   - 切换到 XTTS-v2 模型
   - 支持中文、英文等多语言

4. **流式 TTS**
   - 使用 WebSocket 流式返回音频
   - 边合成边播放，降低延迟
