# VLLM Wrapper 服务部署指南

VLLM Wrapper 是一个 FastAPI 服务，为 VLLM 提供简化的对话接口。支持本地和 Modal 云端部署。

## 特性

- ✅ 简化的对话接口（`/chat`）
- ✅ OpenAI 兼容接口（`/v1/chat/completions`）
- ✅ 流式和非流式响应
- ✅ 健康检查和模型列表
- ✅ API Key 认证（可选）
- ✅ 自动重试和错误处理
- ✅ 本地和云端部署支持

---

## 方式一：本地部署

### 1. 安装依赖

```bash
pip install fastapi uvicorn pydantic openai httpx
```

### 2. 配置环境变量

在项目根目录的 `.env` 文件中添加：

```bash
# VLLM 后端配置
VLLM_BASE_URL=https://ybpang-1--vllm-llama70b-serve-vllm.modal.run/v1
VLLM_MODEL=meta-llama/Llama-3.1-70B-Instruct
VLLM_API_KEY=<your-vllm-api-key>

# Wrapper 服务配置
VLLM_WRAPPER_HOST=0.0.0.0
VLLM_WRAPPER_PORT=8001
VLLM_WRAPPER_API_KEY=your-service-api-key  # 可选，保护你的服务

# 默认参数（可选）
VLLM_DEFAULT_MAX_TOKENS=2048
VLLM_DEFAULT_TEMPERATURE=0.7
VLLM_MAX_RETRIES=3
VLLM_TIMEOUT=60
```

### 3. 启动服务

```bash
# 方法1: 直接运行
python vllm_wrapper.py

# 方法2: 使用 uvicorn
uvicorn vllm_wrapper:app --host 0.0.0.0 --port 8001 --reload
```

服务启动后访问：
- API 文档：http://localhost:8001/docs
- 健康检查：http://localhost:8001/health

---

## 方式二：Modal 云端部署

### 1. 更新 Modal Secret

确保 `vllm-secrets` 包含以下配置：

```bash
modal secret create vllm-secrets \
  VLLM_BASE_URL=https://ybpang-1--vllm-llama70b-serve-vllm.modal.run/v1 \
  VLLM_MODEL=meta-llama/Llama-3.1-70B-Instruct \
  VLLM_API_KEY=<your-vllm-api-key> \
  VLLM_WRAPPER_API_KEY=your-service-api-key
```

或通过 Web UI 编辑：https://modal.com/secrets

### 2. 部署到 Modal

```bash
modal deploy modal_vllm_wrapper.py
```

部署成功后会返回服务 URL，例如：
```
https://ybpang-1--vllm-wrapper-fastapi-app.modal.run
```

### 3. 查看日志

```bash
modal app logs vllm-wrapper
```

---

## API 使用示例

### 1. 健康检查

```bash
curl http://localhost:8001/health
```

响应：
```json
{
  "status": "healthy",
  "vllm_available": true,
  "model": "meta-llama/Llama-3.1-70B-Instruct",
  "base_url": "https://ybpang-1--vllm-llama70b-serve-vllm.modal.run/v1"
}
```

### 2. 列出模型

```bash
curl http://localhost:8001/models
```

### 3. 简化对话接口（非流式）

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-service-api-key" \
  -d '{
    "messages": [
      {"role": "system", "content": "你是一个有帮助的AI助手"},
      {"role": "user", "content": "你好，请介绍一下你自己"}
    ],
    "max_tokens": 512,
    "temperature": 0.7
  }'
```

响应：
```json
{
  "content": "你好！我是一个AI助手...",
  "model": "meta-llama/Llama-3.1-70B-Instruct",
  "usage": {
    "prompt_tokens": 25,
    "completion_tokens": 150,
    "total_tokens": 175
  },
  "finish_reason": "stop"
}
```

### 4. 简化对话接口（流式）

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-service-api-key" \
  -d '{
    "messages": [
      {"role": "user", "content": "写一首短诗"}
    ],
    "stream": true,
    "max_tokens": 200
  }'
```

### 5. OpenAI 兼容接口

```bash
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-service-api-key" \
  -d '{
    "model": "meta-llama/Llama-3.1-70B-Instruct",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ],
    "temperature": 0.7,
    "max_tokens": 100
  }'
```

---

## Python 客户端示例

### 非流式对话

```python
import httpx
import asyncio

async def chat_example():
    url = "http://localhost:8001/chat"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer your-service-api-key"
    }
    payload = {
        "messages": [
            {"role": "system", "content": "你是一个有帮助的AI助手"},
            {"role": "user", "content": "什么是机器学习？"}
        ],
        "max_tokens": 500,
        "temperature": 0.7
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
        result = response.json()
        print(f"回复: {result['content']}")
        print(f"模型: {result['model']}")
        print(f"Token使用: {result['usage']}")

asyncio.run(chat_example())
```

### 流式对话

```python
import httpx
import asyncio

async def chat_stream_example():
    url = "http://localhost:8001/chat"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer your-service-api-key"
    }
    payload = {
        "messages": [
            {"role": "user", "content": "写一个Python函数计算斐波那契数列"}
        ],
        "stream": True,
        "max_tokens": 500
    }

    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, json=payload, headers=headers) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    content = line[6:]  # 去掉 "data: " 前缀
                    if content == "[DONE]":
                        break
                    print(content, end="", flush=True)
        print()  # 换行

asyncio.run(chat_stream_example())
```

### 使用 OpenAI SDK

```python
from openai import AsyncOpenAI

async def openai_sdk_example():
    client = AsyncOpenAI(
        base_url="http://localhost:8001/v1",
        api_key="your-service-api-key"
    )

    response = await client.chat.completions.create(
        model="meta-llama/Llama-3.1-70B-Instruct",
        messages=[
            {"role": "user", "content": "介绍一下Python的装饰器"}
        ],
        temperature=0.7,
        max_tokens=500
    )

    print(response.choices[0].message.content)

import asyncio
asyncio.run(openai_sdk_example())
```

---

## 集成到现有后端

在你的主后端 `backend/main.py` 中，可以轻松调用 VLLM Wrapper：

```python
import httpx

async def call_vllm_wrapper(messages: list):
    """通过 VLLM Wrapper 发送对话请求"""
    url = "http://localhost:8001/chat"  # 或 Modal 部署的 URL
    headers = {
        "Authorization": "Bearer your-service-api-key"
    }
    payload = {
        "messages": messages,
        "max_tokens": 1024,
        "temperature": 0.7
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        result = response.json()
        return result["content"]
```

---

## 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| `VLLM_BASE_URL` | VLLM 服务地址 | `http://localhost:8000/v1` | ✅ |
| `VLLM_MODEL` | 模型名称 | `meta-llama/Llama-3.1-70B-Instruct` | ✅ |
| `VLLM_API_KEY` | VLLM API 密钥 | 空 | ❌ |
| `VLLM_WRAPPER_HOST` | 服务监听地址 | `0.0.0.0` | ❌ |
| `VLLM_WRAPPER_PORT` | 服务端口 | `8001` | ❌ |
| `VLLM_WRAPPER_API_KEY` | 服务层 API 密钥 | 空（禁用认证） | ❌ |
| `VLLM_DEFAULT_MAX_TOKENS` | 默认最大 token 数 | `2048` | ❌ |
| `VLLM_DEFAULT_TEMPERATURE` | 默认温度参数 | `0.7` | ❌ |
| `VLLM_MAX_RETRIES` | 最大重试次数 | `3` | ❌ |
| `VLLM_TIMEOUT` | 请求超时（秒） | `60` | ❌ |

### API Key 认证

如果设置了 `VLLM_WRAPPER_API_KEY`，所有请求都需要在 Header 中提供认证：

```bash
Authorization: Bearer your-service-api-key
```

如果未设置，则不需要认证（适合内网部署）。

---

## 监控和运维

### 本地部署

查看日志：
```bash
# 服务会输出详细日志到标准输出
```

### Modal 部署

查看实时日志：
```bash
modal app logs vllm-wrapper
```

查看应用状态：
```bash
modal app list
```

停止服务：
```bash
modal app stop vllm-wrapper
```

---

## 故障排除

### 问题 1: VLLM 连接失败

**症状**: `/health` 返回 `vllm_available: false`

**解决方案**:
1. 检查 `VLLM_BASE_URL` 是否正确
2. 检查 VLLM 服务是否在运行
3. 检查 `VLLM_API_KEY` 是否正确（如果需要）
4. 查看日志获取详细错误信息

### 问题 2: 401 Unauthorized

**症状**: 请求返回 401 错误

**解决方案**:
1. 确保请求中包含 `Authorization` header
2. 检查 API key 是否与 `VLLM_WRAPPER_API_KEY` 匹配
3. 确认 token 格式为 `Bearer <token>`

### 问题 3: 503 Service Unavailable

**症状**: 请求返回 503 错误

**解决方案**:
1. VLLM 后端可能正在冷启动（Modal 部署）
2. 等待 2-5 分钟后重试
3. 检查 VLLM 服务日志

### 问题 4: 超时错误

**症状**: 请求超时

**解决方案**:
1. 增加 `VLLM_TIMEOUT` 环境变量
2. 减少 `max_tokens` 参数
3. 检查 VLLM 服务负载

---

## 性能优化

1. **流式响应**: 对于长文本生成，使用 `stream: true` 获得更好的用户体验
2. **连接池**: httpx 客户端会自动管理连接池
3. **并发限制**: Modal 部署会自动处理并发和扩展
4. **缓存**: 可以添加 Redis 缓存常见对话

---

## 安全建议

1. **生产环境**: 务必设置 `VLLM_WRAPPER_API_KEY` 保护服务
2. **HTTPS**: Modal 部署自动提供 HTTPS，本地部署建议使用 nginx 反向代理
3. **CORS**: 根据需要限制 `allow_origins`
4. **速率限制**: 可以添加 fastapi-limiter 进行速率限制

---

## 下一步

- [ ] 添加对话历史管理
- [ ] 集成到主后端 `backend/main.py`
- [ ] 添加 WebSocket 支持实时流式对话
- [ ] 添加速率限制和请求配额
- [ ] 添加 Prometheus 监控指标
- [ ] 支持多模型负载均衡

---

## 相关文档

- [VLLM Modal 部署指南](./VLLM_MODAL_DEPLOYMENT.md)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [OpenAI API 参考](https://platform.openai.com/docs/api-reference)
