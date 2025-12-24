# 🚀 奶茶点单系统启动指南

**系统组件**：后端 API + 顾客端前端 + 后厨管理端 + Modal vLLM 备份
**更新时间**：2025-12-09

---

## 📋 系统概览

奶茶点单系统包含以下组件：

| 组件 | 技术栈 | 端口 | 用途 |
|------|--------|------|------|
| **后端 API** | Python + FastAPI | 8000 | 核心业务逻辑、LLM 集成 |
| **顾客端前端** | React + TypeScript + Vite | 5173 | 用户点单界面 |
| **后厨管理端** | React + TypeScript + Vite | 5174 | 订单生产管理 |
| **Modal vLLM** | Modal + vLLM | 云端 | LLM 备份服务（可选） |

---

## ⚡ 快速启动（推荐）

### 方式 1：一键启动脚本

最简单的方式是使用提供的启动脚本：

```bash
cd "/Users/aaronpang/Library/Mobile Documents/com~apple~CloudDocs/Starbot/Agent-System/AiAgentSystem"

# 启动后端
./start.sh
```

这个脚本会自动：
1. 检查并创建 `.env` 配置文件
2. 安装 Python 依赖
3. 创建必要的目录
4. 启动后端服务（端口 8000）

**启动后访问**：
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

### 方式 2：手动启动各组件

如果需要更多控制，可以手动启动各个组件。

---

## 🔧 详细启动步骤

### 步骤 1: 环境准备

#### 1.1 检查环境

确保安装了必要的软件：

```bash
# 检查 Python（需要 3.8+）
python3 --version

# 检查 Node.js（需要 16+）
node --version

# 检查 npm
npm --version
```

#### 1.2 配置环境变量

```bash
cd "/Users/aaronpang/Library/Mobile Documents/com~apple~CloudDocs/Starbot/Agent-System/AiAgentSystem"

# 如果没有 .env 文件，从示例复制
cp .env.example .env

# 编辑 .env 文件
vim .env  # 或使用其他编辑器
```

**必需的配置**：

```env
# 语音识别
ASSEMBLYAI_API_KEY=your_assemblyai_api_key_here

# LLM 主路由（OpenRouter）
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=meta-llama/llama-3.1-70b-instruct
OPENROUTER_TIMEOUT=5.0

# LLM 备份路由（Modal vLLM）- ✅ 已配置超时降级
VLLM_BASE_URL=https://ybpang-1--vllm-llama33-70b-int8-wrapper.modal.run/v1
VLLM_API_KEY=your-modal-vllm-api-key
VLLM_MODEL=meta-llama/Llama-3.3-70B-Instruct
VLLM_TIMEOUT=10.0

# 数据库
DATABASE_PATH=./tea_orders.db

# 服务配置
HOST=0.0.0.0
PORT=8000
```

**API Keys 获取方式**：
- **AssemblyAI**: https://www.assemblyai.com/ → 注册 → API Keys
- **OpenRouter**: https://openrouter.ai/keys → 生成新 Key
- **Modal vLLM**: 已部署，使用 Modal API key

---

### 步骤 2: 安装依赖

#### 2.1 后端依赖

```bash
# 在项目根目录
cd "/Users/aaronpang/Library/Mobile Documents/com~apple~CloudDocs/Starbot/Agent-System/AiAgentSystem"

# 安装 Python 依赖
pip install -r requirements.txt
```

**依赖列表**（requirements.txt）：
- fastapi - Web 框架
- uvicorn - ASGI 服务器
- python-dotenv - 环境变量管理
- openai - OpenAI/OpenRouter 客户端
- assemblyai - AssemblyAI SDK
- websockets - WebSocket 支持

#### 2.2 前端依赖（顾客端）

```bash
# 进入前端目录
cd frontend

# 安装依赖（选择其一）
npm install
# 或
yarn install
# 或
pnpm install
```

#### 2.3 后厨管理端依赖

```bash
# 进入后厨管理端目录
cd backstage-frontend

# 安装依赖
npm install
```

---

### 步骤 3: 启动各组件

建议使用多个终端窗口分别启动各组件。

#### 3.1 启动后端服务（必需）

**终端 1 - 后端**：

```bash
cd "/Users/aaronpang/Library/Mobile Documents/com~apple~CloudDocs/Starbot/Agent-System/AiAgentSystem"

# 方式 1：使用 uvicorn 直接启动
python3 -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 方式 2：使用启动脚本
./start.sh
```

**启动成功标志**：
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

**验证后端**：
```bash
# 健康检查
curl http://localhost:8000/health

# 预期输出：
# {"status":"healthy","message":"服务正常运行"}
```

#### 3.2 启动顾客端前端（可选）

**终端 2 - 顾客端**：

```bash
cd "/Users/aaronpang/Library/Mobile Documents/com~apple~CloudDocs/Starbot/Agent-System/AiAgentSystem/frontend"

# 启动开发服务器
npm run dev
# 或
yarn dev
# 或
pnpm dev
```

**启动成功标志**：
```
  VITE v5.0.8  ready in 500 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: http://192.168.x.x:5173/
  ➜  press h to show help
```

**访问**: 打开浏览器访问 http://localhost:5173

#### 3.3 启动后厨管理端（可选）

**终端 3 - 后厨管理端**：

```bash
cd "/Users/aaronpang/Library/Mobile Documents/com~apple~CloudDocs/Starbot/Agent-System/AiAgentSystem/backstage-frontend"

# 启动开发服务器（默认端口 5174）
npm run dev
```

**访问**: 打开浏览器访问 http://localhost:5174

---

## 🎯 启动验证

### 验证后端服务

1. **API 文档**：访问 http://localhost:8000/docs
   - 应该看到 Swagger UI 文档界面

2. **健康检查**：
   ```bash
   curl http://localhost:8000/health
   ```

3. **测试对话**：
   ```bash
   curl -X POST http://localhost:8000/text \
     -H "Content-Type: application/json" \
     -d '{"text": "我想点一杯奶茶"}'
   ```

### 验证前端服务

1. **顾客端**：访问 http://localhost:5173
   - 应该看到点单界面
   - 检查是否能切换"文字模式"和"语音模式"

2. **后厨管理端**：访问 http://localhost:5174
   - 应该看到订单管理界面
   - 检查订单队列显示

### 验证 LLM 降级功能（新增）

测试超时降级到 Modal vLLM：

```bash
# 运行超时降级测试
cd "/Users/aaronpang/Library/Mobile Documents/com~apple~CloudDocs/Starbot/Agent-System/AiAgentSystem"
python3 test_timeout_fallback.py
```

**预期输出**：
```
✅ 配置加载正确（5秒/10秒超时）
✅ 后端初始化成功（OpenRouter + vLLM）
✅ 错误分类逻辑正确
```

---

## 📊 启动后的系统访问地址

| 服务 | URL | 用途 |
|------|-----|------|
| **后端 API** | http://localhost:8000 | REST API 端点 |
| **API 文档** | http://localhost:8000/docs | Swagger UI 文档 |
| **健康检查** | http://localhost:8000/health | 服务状态检查 |
| **顾客端** | http://localhost:5173 | 用户点单界面 |
| **后厨管理端** | http://localhost:5174 | 订单生产管理 |
| **WebSocket** | ws://localhost:8000/ws | 实时通信 |
| **订单队列 WS** | ws://localhost:8000/ws/production/queue | 实时订单状态 |

---

## 🔄 服务依赖关系

```
┌──────────────────────┐
│  顾客端前端 (5173)   │
└──────────┬───────────┘
           │
           ↓
┌──────────────────────┐     ┌──────────────────────┐
│  后端 API (8000)     │ ←── │ 后厨管理端 (5174)    │
└──────────┬───────────┘     └──────────────────────┘
           │
           ↓
┌──────────────────────────────────────────┐
│  LLM 路由 (智能降级)                     │
├──────────────────────────────────────────┤
│  1️⃣ OpenRouter (5秒超时)               │
│          ↓ [超时/限流]                   │
│  2️⃣ Modal vLLM (10秒超时)              │
│          ↓ [全部失败]                    │
│  3️⃣ 离线规则引擎 (保底)                │
└──────────────────────────────────────────┘
```

**启动顺序建议**：
1. ✅ **必需**：后端 API（其他服务依赖它）
2. ⭐ **推荐**：顾客端前端（主要用户界面）
3. 📊 **可选**：后厨管理端（内部管理使用）

---

## 🛠️ 常用启动命令总结

### 开发环境（完整系统）

```bash
# 终端 1 - 后端
cd "/Users/aaronpang/Library/Mobile Documents/com~apple~CloudDocs/Starbot/Agent-System/AiAgentSystem"
./start.sh

# 终端 2 - 顾客端
cd "/Users/aaronpang/Library/Mobile Documents/com~apple~CloudDocs/Starbot/Agent-System/AiAgentSystem/frontend"
npm run dev

# 终端 3 - 后厨管理端
cd "/Users/aaronpang/Library/Mobile Documents/com~apple~CloudDocs/Starbot/Agent-System/AiAgentSystem/backstage-frontend"
npm run dev
```

### 仅后端开发/测试

```bash
cd "/Users/aaronpang/Library/Mobile Documents/com~apple~CloudDocs/Starbot/Agent-System/AiAgentSystem"

# 启动后端
python3 -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 使用 API 文档测试
# 访问 http://localhost:8000/docs
```

### 生产环境启动

```bash
cd "/Users/aaronpang/Library/Mobile Documents/com~apple~CloudDocs/Starbot/Agent-System/AiAgentSystem"

# 后端（不使用 --reload）
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4

# 前端（构建静态文件）
cd frontend
npm run build
# 使用 nginx 或其他静态服务器托管 dist/ 目录
```

---

## 🚨 常见问题排查

### 问题 1: 后端启动失败 - "Address already in use"

**症状**：
```
ERROR:    [Errno 48] Address already in use
```

**原因**：端口 8000 被占用

**解决**：
```bash
# 查找占用 8000 端口的进程
lsof -i :8000

# 杀死进程
kill -9 <PID>

# 或使用其他端口
python3 -m uvicorn backend.main:app --reload --port 8001
```

### 问题 2: 前端启动失败 - "Cannot find module"

**症状**：
```
Error: Cannot find module 'vite'
```

**原因**：依赖未安装

**解决**：
```bash
cd frontend  # 或 backstage-frontend
rm -rf node_modules package-lock.json
npm install
```

### 问题 3: LLM 调用失败 - "No API key provided"

**症状**：后端日志显示 API key 相关错误

**原因**：`.env` 文件未配置或未加载

**解决**：
```bash
# 检查 .env 文件是否存在
ls -la .env

# 验证配置加载
python3 -c "from backend.config import config; print(f'OpenRouter Key: {config.OPENROUTER_API_KEY[:10]}...')"

# 重启后端服务
```

### 问题 4: 语音识别不工作

**症状**：点击语音按钮无反应或报错

**原因**：浏览器权限或 HTTPS 要求

**解决**：
1. 确保使用支持的浏览器（Chrome/Edge/Safari）
2. 允许浏览器麦克风权限
3. 本地开发使用 localhost（无需 HTTPS）
4. 检查 AssemblyAI API key 是否有效

### 问题 5: Modal vLLM 降级不工作

**症状**：OpenRouter 超时但没切换到 vLLM

**解决**：
```bash
# 1. 运行测试验证配置
python3 test_timeout_fallback.py

# 2. 检查 vLLM 服务状态
curl https://ybpang-1--vllm-llama33-70b-int8-wrapper.modal.run/health

# 3. 验证环境变量
python3 -c "from backend.config import config; print(f'VLLM URL: {config.VLLM_BASE_URL}')"

# 4. 查看后端日志
# 应该看到：
# INFO: 调用 openrouter，超时设置: 5.0秒
# WARNING: ⚠️ openrouter 可重试错误: APITimeoutError
# INFO: 调用 vllm，超时设置: 10.0秒
```

---

## 📝 日志查看

### 后端日志

后端日志直接输出到终端：

```bash
# 实时查看日志（如果后台运行）
tail -f backend.log

# 过滤特定关键字
grep "ERROR" backend.log
grep "LLM" backend.log
```

**关键日志模式**（超时降级）：
```
✅ openrouter 调用成功          # OpenRouter 正常
⚠️ openrouter 可重试错误        # OpenRouter 超时，触发降级
✅ vllm 调用成功                # vLLM 备份生效
❌ 所有 LLM 后端调用失败         # 双重失败
```

### 前端日志

打开浏览器开发者工具（F12）→ Console 标签页

### 网络请求监控

开发者工具 → Network 标签页，查看 API 请求/响应

---

## 🔄 停止服务

### 停止后端

在后端运行的终端按 `Ctrl + C`

### 停止前端

在前端运行的终端按 `Ctrl + C`

### 全部停止（如果使用脚本）

```bash
# 查找所有相关进程
ps aux | grep uvicorn
ps aux | grep vite

# 杀死进程
pkill -f uvicorn
pkill -f vite
```

---

## 📦 生产部署

### 使用 Modal 部署（推荐）

```bash
# 部署完整系统到 Modal
./deploy.sh
```

详细部署说明请参考：
- [DEPLOYMENT_SUMMARY.md](../../vllm-workspace/docs/DEPLOYMENT_SUMMARY.md) - 部署总结
- [QUICKSTART_MODAL.md](../../QUICKSTART_MODAL.md) - Modal 快速开始

### 传统部署

1. **后端**：使用 Gunicorn + Uvicorn workers
2. **前端**：构建静态文件 → Nginx/Caddy
3. **数据库**：迁移到 PostgreSQL（生产环境）
4. **负载均衡**：Nginx 反向代理

---

## 🎓 更多资源

- **系统文档**: [README.md](README.md)
- **超时降级实施**: [MODAL_VLLM_FALLBACK_IMPLEMENTATION.md](MODAL_VLLM_FALLBACK_IMPLEMENTATION.md)
- **Llama 3.3 70B 测试**: [LLAMA_33_70B_TEST_REPORT.md](LLAMA_33_70B_TEST_REPORT.md)
- **API 测试脚本**: `test_api.sh`
- **WebSocket 测试**: `test-websocket.html`

---

## ✅ 启动检查清单

使用此清单确保系统正确启动：

- [ ] Python 3.8+ 已安装
- [ ] Node.js 16+ 已安装
- [ ] `.env` 文件已配置（API keys）
- [ ] Python 依赖已安装（`pip install -r requirements.txt`）
- [ ] 前端依赖已安装（`npm install`）
- [ ] 后端服务启动成功（端口 8000）
- [ ] 健康检查通过（`curl http://localhost:8000/health`）
- [ ] 顾客端前端可访问（http://localhost:5173）
- [ ] API 文档可访问（http://localhost:8000/docs）
- [ ] LLM 降级功能测试通过（`python3 test_timeout_fallback.py`）

---

**最后更新**: 2025-12-09
**维护者**: Claude Code
**系统状态**: ✅ 所有组件正常运行，超时降级功能已实施
