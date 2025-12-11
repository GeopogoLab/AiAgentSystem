# VLLM Modal 部署指南

本指南将帮助你将 VLLM 后端部署到 Modal，使用单张 A100-80G GPU 运行 Llama 3.1 70B 模型。

## 前置要求

1. **安装 Modal CLI**
```bash
pip install modal
```

2. **Modal 账户认证**
```bash
modal token new
```

3. **创建 Modal Secret**

需要在 Modal 平台创建名为 `vllm-secrets` 的 Secret，包含以下环境变量：

- `HUGGING_FACE_HUB_TOKEN`: Hugging Face Token（用于下载模型）
  - 获取地址: https://huggingface.co/settings/tokens
  - 需要接受 Llama 模型的使用协议: https://huggingface.co/meta-llama/Llama-3.1-70B-Instruct

- `VLLM_SERVER_API_KEY`（可选）: 用于保护 API 端点的密钥

**创建 Secret 步骤：**
```bash
# 方法 1: 通过 CLI
modal secret create vllm-secrets \
  HUGGING_FACE_HUB_TOKEN=hf_... \
  VLLM_SERVER_API_KEY=your-secret-key

# 方法 2: 通过 Web UI
# 访问 https://modal.com/secrets，点击 "New secret"
```

## 部署步骤

### 1. 部署 VLLM 服务

```bash
modal deploy modal_vllm.py
```

部署成功后，Modal 会返回一个 URL，格式类似：
```
https://your-workspace--vllm-llama70b-serve-vllm.modal.run
```

### 2. 获取完整 API 端点

VLLM OpenAI 兼容 API 的完整 URL 为：
```
https://your-workspace--vllm-llama70b-serve-vllm.modal.run/v1
```

### 3. 配置环境变量

在项目根目录的 `.env` 文件中添加：

```bash
# VLLM Modal 配置
VLLM_BASE_URL=https://your-workspace--vllm-llama70b-serve-vllm.modal.run/v1
VLLM_MODEL=meta-llama/Llama-3.1-70B-Instruct
VLLM_API_KEY=your-secret-key  # 与 Modal Secret 中的 VLLM_SERVER_API_KEY 相同
```

## 配置说明

### GPU 配置
- **GPU 类型**: A100-80G
- **GPU 数量**: 1 张
- **Tensor Parallel**: 1（不需要模型并行）
- **显存利用率**: 0.95（95%）
- **最大上下文长度**: 8192 tokens

### 性能优化
- 单张 A100-80G 足够运行 Llama 3.1 70B 模型
- 增大 `MAX_MODEL_LEN` 到 8192 以支持更长的上下文
- 提高 `GPU_MEMORY_UTILIZATION` 到 0.95 以充分利用显存

### 成本控制
- **Container Idle Timeout**: 15 分钟（无请求时自动停止）
- **Timeout**: 24 小时（最长运行时间）
- **Cold Start**: 首次请求需要 2-5 分钟加载模型

## 测试部署

### 测试 API 连接

```bash
curl https://your-workspace--vllm-llama70b-serve-vllm.modal.run/v1/models \
  -H "Authorization: Bearer your-secret-key"
```

### 测试对话生成

```bash
curl https://your-workspace--vllm-llama70b-serve-vllm.modal.run/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-key" \
  -d '{
    "model": "meta-llama/Llama-3.1-70B-Instruct",
    "messages": [
      {"role": "user", "content": "你好，请介绍一下你自己"}
    ],
    "temperature": 0.7,
    "max_tokens": 512
  }'
```

## 环境变量自定义

可以通过修改 `modal_vllm.py` 或设置环境变量来自定义配置：

```bash
# 修改模型
export VLLM_MODEL="meta-llama/Llama-3.3-70B-Instruct"

# 修改上下文长度
export VLLM_MAX_MODEL_LEN="16384"

# 修改显存利用率
export VLLM_GPU_MEMORY_UTILIZATION="0.90"

# 然后重新部署
modal deploy modal_vllm.py
```

## 监控和日志

### 查看实时日志
```bash
modal app logs vllm-llama70b
```

### 查看应用状态
访问 Modal Dashboard: https://modal.com/apps

## 故障排除

### 问题 1: 模型下载失败
- 确认 `HUGGING_FACE_HUB_TOKEN` 已正确设置
- 确认已接受 Llama 模型使用协议

### 问题 2: OOM (Out of Memory)
- 降低 `VLLM_MAX_MODEL_LEN`
- 降低 `VLLM_GPU_MEMORY_UTILIZATION` 到 0.90

### 问题 3: Cold Start 时间过长
- 这是正常现象，首次加载需要下载和加载模型
- 后续请求会使用缓存的模型权重

### 问题 4: API 认证失败
- 确认 `VLLM_API_KEY` 与 Modal Secret 中的 `VLLM_SERVER_API_KEY` 一致
- 检查请求头中的 `Authorization: Bearer <token>` 格式

## 更新部署

修改代码后重新部署：
```bash
modal deploy modal_vllm.py
```

## 停止服务

```bash
modal app stop vllm-llama70b
```

## 费用估算

- A100-80G: 约 $3.12/小时
- 使用 Container Idle Timeout 可以大幅降低成本
- 建议监控使用情况，按需调整配置
