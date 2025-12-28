# 本地 TTS 服务部署指南

## 概述

这是一个基于 Coqui TTS 的本地文本转语音 (TTS) FastAPI 服务，支持离线运行，无需外部 API。

## 已部署的服务

✅ **服务状态**: 运行中
🌐 **服务地址**: `http://localhost:8002`
📚 **API 文档**: `http://localhost:8002/docs`
🤖 **模型**: `tts_models/en/ljspeech/tacotron2-DDC`
💻 **设备**: CPU

## 快速开始

### 1. 启动服务

```bash
# 默认端口 8001
python3 tts_service.py

# 指定端口
PORT=8002 python3 tts_service.py

# 使用 GPU
LOCAL_TTS_DEVICE=cuda python3 tts_service.py
```

### 2. 测试服务

```bash
# 运行完整测试
python3 test_tts_api.py

# 播放生成的音频
afplay api_test_1.wav
afplay api_test_2.wav
```

## API 端点

### 1. 健康检查

```bash
curl http://localhost:8002/health
```

**响应:**
```json
{
  "status": "ok",
  "model": "tts_models/en/ljspeech/tacotron2-DDC",
  "device": "cpu"
}
```

### 2. 列出可用模型

```bash
curl http://localhost:8002/models
```

### 3. 文本转语音

```bash
curl -X POST http://localhost:8002/tts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, this is a test.",
    "voice": null,
    "format": "wav"
  }'
```

**响应:**
```json
{
  "audio_base64": "UklGRuaXBBW...",
  "voice": "default",
  "format": "wav",
  "text": "Hello, this is a test.",
  "duration_sec": 1.84
}
```

## Python 客户端示例

```python
import base64
import requests
from pathlib import Path

# 发送 TTS 请求
response = requests.post(
    "http://localhost:8002/tts",
    json={
        "text": "Hello world!",
        "format": "wav"
    }
)

# 保存音频
if response.status_code == 200:
    data = response.json()
    audio_bytes = base64.b64decode(data['audio_base64'])
    Path("output.wav").write_bytes(audio_bytes)
    print(f"✅ 音频已保存，时长: {data['duration_sec']:.2f} 秒")
```

## JavaScript/cURL 示例

```bash
# 保存音频到文件
curl -X POST http://localhost:8002/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello from TTS API"}' \
  | jq -r '.audio_base64' \
  | base64 -d > output.wav
```

## 配置选项

通过环境变量配置服务：

```bash
# .env 文件
LOCAL_TTS_MODEL=tts_models/en/ljspeech/tacotron2-DDC
LOCAL_TTS_DEVICE=cpu          # 或 cuda
LOCAL_TTS_FORMAT=wav
HOST=0.0.0.0
PORT=8002
```

## 可用模型

| 模型 | 语言 | 质量 | 速度 |
|------|------|------|------|
| `tts_models/en/ljspeech/tacotron2-DDC` | 英语 | 高 | 中 |
| `tts_models/en/ljspeech/glow-tts` | 英语 | 高 | 快 |
| `tts_models/en/vctk/vits` | 英语 | 高 | 中 |
| `tts_models/multilingual/multi-dataset/xtts_v2` | 多语言 | 极高 | 慢 |

## 性能优化

### 使用 GPU 加速

```bash
# 修改 .env
LOCAL_TTS_DEVICE=cuda

# 或启动时指定
LOCAL_TTS_DEVICE=cuda python3 tts_service.py
```

### 切换更快的模型

```bash
LOCAL_TTS_MODEL=tts_models/en/ljspeech/glow-tts python3 tts_service.py
```

## 集成到现有应用

### 替换 AssemblyAI TTS

在 `backend/main.py` 中修改 TTS 路由：

```python
@app.post("/tts")
async def tts_endpoint(request: TTSRequest):
    # 调用本地 TTS 服务
    response = requests.post(
        "http://localhost:8002/tts",
        json={"text": request.text}
    )
    return response.json()
```

## 故障排查

### 端口被占用

```bash
# 查看占用端口的进程
lsof -i :8002

# 使用其他端口
PORT=8003 python3 tts_service.py
```

### 模型下载失败

模型会自动下载到 `~/.local/share/tts/`，确保网络连接正常。

### 内存不足

使用更小的模型或增加系统 swap。

## 测试结果

✅ 所有测试通过:
- 健康检查: ✓
- 模型列表: ✓ (8 个可用模型)
- TTS 合成: ✓ (2 个测试用例)
- 音频生成: ✓ (`api_test_1.wav`, `api_test_2.wav`)

## 文件说明

- `tts_service.py` - FastAPI TTS 服务
- `test_tts_api.py` - API 测试客户端
- `test_local_tts.py` - 直接 TTS 测试（无 API）
- `TTS_DEPLOYMENT_GUIDE.md` - 本文档

## 下一步

1. **生产部署**: 使用 Gunicorn + Nginx
2. **监控**: 添加日志和指标
3. **缓存**: 缓存常用语音片段
4. **多语言**: 切换到 XTTS-v2 支持中文

## 相关链接

- Coqui TTS: https://github.com/coqui-ai/TTS
- FastAPI: https://fastapi.tiangolo.com
- 服务文档: http://localhost:8002/docs
