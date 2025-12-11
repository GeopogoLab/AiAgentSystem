# VLLM 集成部署指南

## 🎉 部署概览

已成功部署 **vLLM + FastAPI 集成服务** 到 Modal，避免冷启动问题。

### 📍 服务信息

- **服务URL**: `https://ybpang-1--vllm-integrated-serve.modal.run`
- **模型**: Llama-3.1-8B-Instruct
- **GPU**: 1x A100-80GB
- **闲置超时**: 30分钟（无请求后自动休眠）
- **部署文件**: `modal_vllm_integrated.py`

## ✨ 架构优势

### 与之前方案的对比

**之前的架构**（2个独立服务）:
- vLLM服务器（Modal）
- FastAPI Wrapper（本地或单独部署）
- ❌ 每次调用需要通过网络
- ❌ 每个服务独立冷启动
- ❌ 管理复杂

**现在的架构**（集成部署）:
- ✅ vLLM和FastAPI在同一容器中
- ✅ 通过localhost通信，零网络延迟
- ✅ 一次冷启动，服务持续运行
- ✅ 30分钟无请求后自动休眠节省成本
- ✅ 统一部署和管理

## 🚀 快速开始

### 1. 测试服务健康状态

```bash
curl https://ybpang-1--vllm-integrated-serve.modal.run/health
```

响应示例:
```json
{
  "status": "healthy",
  "vllm_available": true,
  "model": "meta-llama/Llama-3.1-8B-Instruct"
}
```

### 2. 发送对话请求（简化接口）

```bash
curl -X POST https://ybpang-1--vllm-integrated-serve.modal.run/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Hello! How are you?"}
    ],
    "max_tokens": 100,
    "temperature": 0.7
  }'
```

### 3. 使用OpenAI兼容接口

```bash
curl -X POST https://ybpang-1--vllm-integrated-serve.modal.run/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "messages": [
      {"role": "user", "content": "Write a haiku about AI"}
    ],
    "max_tokens": 50
  }'
```

### 4. 在Python中使用

```python
import httpx
import asyncio

async def call_vllm():
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://ybpang-1--vllm-integrated-serve.modal.run/chat",
            json={
                "messages": [
                    {"role": "user", "content": "Explain quantum computing"}
                ],
                "max_tokens": 200,
                "temperature": 0.7
            }
        )
        result = response.json()
        print(result["content"])

asyncio.run(call_vllm())
```

## 📡 API端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/` | GET | 服务信息 |
| `/health` | GET | 健康检查 |
| `/models` | GET | 列出可用模型 |
| `/chat` | POST | 简化对话接口 |
| `/v1/chat/completions` | POST | OpenAI兼容接口 |

## 🔧 重新部署

如需更新配置或重新部署:

```bash
cd /path/to/AiAgentSystem
modal deploy modal_vllm_integrated.py
```

## ⚙️ 配置选项

在 `modal_vllm_integrated.py` 中可以修改:

```python
# 切换模型（需要重新部署）
VLLM_MODEL = "meta-llama/Llama-3.1-8B-Instruct"  # 或其他模型

# GPU配置
GPU_COUNT = 1  # A100 GPU数量
VLLM_TENSOR_PARALLEL = 1  # Tensor并行度

# 显存配置
VLLM_GPU_MEMORY_UTILIZATION = 0.90  # 显存利用率

# 超时配置
CONTAINER_IDLE_TIMEOUT = 30 * 60  # 30分钟
```

### 使用70B模型

如果需要使用70B模型，修改配置并使用2个GPU:

```python
VLLM_MODEL = "meta-llama/Llama-3.1-70B-Instruct"
GPU_COUNT = 2
VLLM_TENSOR_PARALLEL = 2
```

然后在函数装饰器中:
```python
@app.function(
    gpu="A100-80GB:2",  # 2个GPU
    ...
)
```

**注意**: 70B模型成本约为8B模型的2倍。

## 💰 成本优化

- **8B模型**: ~$1.10/小时（单个A100-80GB）
- **70B模型**: ~$2.20/小时（2个A100-80GB）
- **自动休眠**: 30分钟无请求后自动scale到0，不产生GPU成本
- **快速冷启动**: 8B模型约1-2分钟，70B模型约3-5分钟

## 📊 监控和日志

查看实时日志:
```bash
modal app logs vllm-integrated
```

查看部署状态:
```bash
modal app list
```

Web界面: https://modal.com/apps/ybpang-1/main/deployed/vllm-integrated

## 🔐 安全配置

### 添加API Key保护

在Modal Secret `vllm-secrets` 中添加:
- `VLLM_WRAPPER_API_KEY`: 保护Wrapper服务

然后在请求时添加Header:
```bash
curl -H "Authorization: Bearer your-api-key" \
  https://ybpang-1--vllm-integrated-serve.modal.run/chat \
  ...
```

## 🐛 故障排查

### 服务返回"invalid function call"
- 服务正在冷启动，等待1-2分钟
- 检查Modal日志: `modal app logs vllm-integrated`

### CUDA out of memory
- 降低 `VLLM_GPU_MEMORY_UTILIZATION` (如0.90 → 0.75)
- 或使用更小的模型（70B → 8B）
- 或增加GPU数量并启用tensor parallelism

### 服务超时
- 首次请求需要下载模型，可能需要5-10分钟
- 后续请求会使用缓存的模型，启动快得多

## 📝 后续步骤

1. ✅ 服务已部署并运行
2. ⏳ 等待首次模型下载完成（约5-10分钟）
3. 📝 更新应用配置以使用新的URL
4. 🧪 运行测试确保集成正常
5. 🚀 投入生产使用

## 🔗 相关文件

- `modal_vllm_integrated.py` - 集成部署配置
- `modal_vllm.py` - 旧版vLLM独立部署（已废弃）
- `vllm_wrapper.py` - FastAPI包装层代码（已集成）
- `modal_vllm_wrapper.py` - Wrapper独立部署（已废弃）

---

**部署时间**: 2025-12-06
**部署者**: Claude Code
**状态**: ✅ 已部署并运行
