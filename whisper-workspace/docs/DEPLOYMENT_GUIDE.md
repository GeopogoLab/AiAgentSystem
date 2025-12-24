# Whisper STT 备用方案部署指南

## 概述

本系统已实现 **Whisper STT 作为 AssemblyAI 的备用方案**，当 AssemblyAI 连接失败或未配置时，自动降级到 Modal 部署的 Whisper 服务。

**核心特性**:
- ✅ **零前端修改**: 前端代码无需任何改动
- ✅ **透明降级**: 3 秒超时自动切换到 Whisper
- ✅ **统一接口**: AssemblyAI 和 Whisper 使用相同的 WebSocket 端点
- ✅ **成本优化**: Whisper GPU 按需启动，3 分钟空闲后自动释放

---

## 已实现的文件

### Modal 部署文件
- `whisper-workspace/modal/modal_whisper_stt.py` - Whisper STT 服务（150 行）
- `whisper-workspace/modal/deploy_whisper.sh` - 部署脚本

### 后端文件
- `backend/config.py` - 新增 STT 配置（+17 行）
- `backend/stt/__init__.py` - STT 模块初始化
- `backend/stt/backends.py` - STT 后端路由器（60 行）
- `backend/main.py` - 重构 `/ws/stt` 端点（~200 行，替换原有 138 行）

### 配置文件
- `.env.example` - 新增 Whisper 环境变量文档

---

## 部署步骤

### 1. Modal 环境准备

**安装 Modal CLI**:
```bash
pip install modal
```

**登录 Modal（选择其中一种方式）**:

方式 1: 浏览器登录（推荐）
```bash
modal token new
```
执行后会打开浏览器，登录 Modal 账户并自动配置 token。

方式 2: 使用现有 token
```bash
modal token set --token-id ak-xxx --token-secret as-xxx
```
从 https://modal.com/settings 获取 token。

**验证登录**:
```bash
modal app list
```

---

### 2. 部署 Whisper 服务

```bash
cd whisper-workspace/modal
./deploy_whisper.sh
```

部署成功后，你会看到类似输出：
```
✅ 部署完成！

接下来的步骤:

1. 获取你的 Modal 用户名:
   modal profile current

2. 将以下内容添加到 .env 文件:
   WHISPER_SERVICE_URL=wss://<your-username>--whisper-stt-wrapper.modal.run/ws/stt
```

---

### 3. 配置环境变量

**获取你的 Modal 用户名**:
```bash
modal profile current
```

**编辑 `.env` 文件**，添加 Whisper 配置:

```bash
# AssemblyAI（主要）
ASSEMBLYAI_API_KEY=your_assemblyai_api_key_here
ASSEMBLYAI_STREAMING_URL=wss://api.assemblyai.com/v2/realtime/ws
ASSEMBLYAI_STREAMING_SAMPLE_RATE=16000
ASSEMBLYAI_STREAMING_ENCODING=pcm_s16le
ASSEMBLYAI_STREAMING_MODEL=best
ASSEMBLYAI_CONNECTION_TIMEOUT=3.0

# Whisper 备用（Modal 部署）
WHISPER_ENABLED=true
WHISPER_SERVICE_URL=wss://<your-username>--whisper-stt-wrapper.modal.run/ws/stt
WHISPER_API_KEY=
WHISPER_MODEL=medium
WHISPER_TIMEOUT=10.0
```

将 `<your-username>` 替换为你的 Modal 用户名。

---

### 4. 测试 Whisper 服务

**测试 health 端点**:
```bash
curl https://<your-username>--whisper-stt-wrapper.modal.run/health
```

预期输出:
```json
{"status":"ok","service":"whisper-stt"}
```

**查看 Modal 日志**:
```bash
modal app logs whisper-stt
```

---

### 5. 重启主后端

```bash
cd backend
./start.sh
```

或使用 uvicorn:
```bash
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 验证降级功能

### 测试场景 1: 正常使用 AssemblyAI

**配置**: 正确配置 `ASSEMBLYAI_API_KEY` 和 `WHISPER_SERVICE_URL`

**测试**:
1. 启动后端和前端
2. 使用前端语音输入功能
3. 查看后端日志，应该看到:
   ```
   INFO: 尝试连接 assemblyai STT 服务...
   INFO: ✅ 成功连接到 assemblyai
   ```

### 测试场景 2: 降级到 Whisper（移除 AssemblyAI Key）

**配置**: 移除或注释掉 `ASSEMBLYAI_API_KEY`

**测试**:
1. 重启后端
2. 使用前端语音输入功能
3. 查看后端日志，应该看到:
   ```
   INFO: 尝试连接 whisper STT 服务...
   INFO: ✅ 成功连接到 whisper
   ```

### 测试场景 3: 降级到 Whisper（AssemblyAI 超时）

**配置**: 使用错误的 `ASSEMBLYAI_API_KEY`

**测试**:
1. 设置 `ASSEMBLYAI_API_KEY=invalid_key`
2. 重启后端
3. 使用前端语音输入功能
4. 查看后端日志，应该看到:
   ```
   INFO: 尝试连接 assemblyai STT 服务...
   WARNING: ⚠️ assemblyai 失败: ClientResponseError: 401
   INFO: 尝试连接 whisper STT 服务...
   INFO: ✅ 成功连接到 whisper
   ```

---

## 系统架构

```
前端 (VoiceInput.tsx)
    ↓ WebSocket (/ws/stt)
主后端 (backend/main.py)
    ↓ STT 路由器 (3秒超时检测)
    ├─ AssemblyAI (优先) → 流式实时识别
    └─ Whisper Modal (降级) → 分段识别（VAD）
        ↓ Modal 部署
        ├─ FastAPI Wrapper (CPU, always-on)
        └─ Whisper Inference (GPU A10G, 按需)
```

**降级逻辑**:
1. 主后端优先尝试连接 AssemblyAI（3 秒超时）
2. 如果超时或连接失败，自动切换到 Whisper
3. 前端收到 `fallback_notice` 消息（可选显示通知）
4. 所有后续语音识别使用 Whisper

---

## 成本和性能

### 延迟对比

| 服务 | 延迟 | 体验 |
|------|------|------|
| AssemblyAI | 200-500ms | 流式，最优 |
| Whisper (热启动) | 800-1500ms/段 | 分段，可接受 |
| Whisper (冷启动) | 10-15秒 | 首次慢，后续正常 |

### 成本对比

| 服务 | 成本 | 说明 |
|------|------|------|
| AssemblyAI | $0.15-0.25/分钟 | 按使用计费 |
| Whisper (A10G) | $0.6/小时 GPU | 3 分钟空闲后释放 |

**推荐策略**: AssemblyAI 主力（质量最优），Whisper 可靠备份（成本可控）

---

## 常见问题

### Q1: 如何查看 Modal 部署状态？

```bash
modal app list
modal app logs whisper-stt
```

### Q2: 如何重新部署 Whisper 服务？

```bash
cd whisper-workspace/modal
./deploy_whisper.sh
```

### Q3: 前端需要修改吗？

不需要！前端代码完全无需修改，降级是透明的。

### Q4: 如何禁用 Whisper 备用？

在 `.env` 中设置:
```bash
WHISPER_ENABLED=false
```

### Q5: Whisper 识别准确率如何？

Whisper Medium 中文识别准确率通常 > 90%，与 AssemblyAI 基本相当。

### Q6: 如何停止 Modal 服务？

```bash
modal app stop whisper-stt
```

### Q7: 降级通知如何在前端显示？

前端 WebSocket 会收到 `fallback_notice` 消息，可选择显示 toast 通知：

```typescript
if (data.message_type === 'fallback_notice') {
  console.info(`STT 已切换到 ${data.to}，原因：${data.reason}`);
  // toast.info('语音识别已切换到备用系统');
}
```

---

## 监控和日志

### 后端日志

正常流程:
```
INFO: 尝试连接 assemblyai STT 服务...
INFO: ✅ 成功连接到 assemblyai
```

降级流程:
```
INFO: 尝试连接 assemblyai STT 服务...
WARNING: ⚠️ assemblyai 失败: TimeoutError
INFO: 尝试连接 whisper STT 服务...
INFO: ✅ 成功连接到 whisper
INFO: 收到最终识别: 你好世界
```

### Modal 日志

```bash
modal app logs whisper-stt --follow
```

示例输出:
```
加载 Whisper medium 模型...
✅ 模型加载完成
处理音频段: 32000 bytes, 2.0秒
✅ 识别完成: 你好世界
```

---

## 故障排查

### 问题 1: Modal 部署失败

**症状**: `modal deploy` 报错

**解决**:
1. 检查 Modal 登录状态: `modal app list`
2. 重新登录: `modal token new`
3. 检查网络连接
4. 查看详细错误信息

### 问题 2: Whisper 服务连接超时

**症状**: 后端日志显示 `whisper 失败: TimeoutError`

**解决**:
1. 检查 Modal 服务状态: `modal app logs whisper-stt`
2. 增加超时时间: `.env` 中设置 `WHISPER_TIMEOUT=20.0`
3. 检查 `WHISPER_SERVICE_URL` 是否正确

### 问题 3: 识别结果为空

**症状**: Whisper 连接成功但识别结果为空

**解决**:
1. 检查音频格式: 确保是 16kHz PCM
2. 检查音频长度: 至少 1 秒
3. 查看 Modal 日志: `modal app logs whisper-stt`
4. 检查 VAD 配置: 可能音频被判定为静音

---

## 下一步

部署完成后，你的系统已具备:
- ✅ 双重 STT 保障（AssemblyAI + Whisper）
- ✅ 自动降级机制（3 秒超时）
- ✅ 前端零修改
- ✅ 成本优化（GPU 按需启动）

建议:
1. 监控 AssemblyAI → Whisper 降级频率
2. 根据实际使用调整超时参数
3. 定期检查 Modal 服务日志
4. 考虑添加降级通知到前端 UI

---

## 技术支持

- Modal 文档: https://modal.com/docs
- Whisper 文档: https://github.com/openai/whisper
- faster-whisper: https://github.com/guillaumekln/faster-whisper

如有问题，请检查:
1. 后端日志 (`./start.sh` 输出)
2. Modal 日志 (`modal app logs whisper-stt`)
3. 网络连接状态
4. 环境变量配置
