# 🧋 奶茶点单 AI Agent 系统

一个基于语音识别和大语言模型的智能奶茶点单系统。用户可以通过语音或文字与 AI 接待员对话，系统会自动收集订单信息（饮品、杯型、甜度、冰块、加料等），并在确认后保存到数据库。

## ✨ 特性

- 🎤 **语音输入**：集成 AssemblyAI 实时 WebSocket 语音识别
- 💬 **智能对话**：使用 OpenRouter · Llama 3.3 70B 实现自然语言交互
- 🔁 **双路容灾**：OpenRouter 主路由，Modal vLLM 70B 自托管备选，自动降级不断线
- 🛠️ **Function Calling**：Agent 自主调用工具查询订单进度和排队状态
- 📝 **文本输入**：支持文字输入模式（方便测试和使用）
- 🗄️ **订单管理**：SQLite 数据库存储订单
- 🎨 **简洁界面**：响应式 Web 界面
- 📊 **会话管理**：保持对话上下文，支持多轮对话
- 📟 **排队面板**：全局展示正在制作 / 已完成的订单，实时 WebSocket 推送
- 💰 **实时报价**：确认订单后自动计算金额，并在前端展示

## 🏗️ 系统架构

```
┌────────────────────────────┐
│   前端界面 (React + TS)    │
│   Vite + Tailwind CSS      │
└──────────┬─────────────────┘
           │
           ↓
┌─────────────────────────────┐
│      FastAPI 后端服务        │
├─────────────────────────────┤
│  ┌──────────────────────┐  │
│  │  AssemblyAI (STT)    │  │  语音转文本
│  └──────────────────────┘  │
│  ┌──────────────────────┐  │
│  │  LLM Agent (OpenRouter · Llama 3.3 70B) │  │  智能对话
│  └──────────────────────┘  │
│  ┌──────────────────────┐  │
│  │  会话管理器          │  │  状态管理
│  └──────────────────────┘  │
│  ┌──────────────────────┐  │
│  │  SQLite 数据库       │  │  订单存储
│  └──────────────────────┘  │
└─────────────────────────────┘
```

LLM 请求顺序：OpenRouter → Modal vLLM 70B 备选 → 规则引擎离线模式，保证弱网或限流场景仍可用。

## 📋 流程说明

### 点单流程
1. **用户输入**：通过语音或文字输入需求
2. **语音识别**：AssemblyAI 实时转为文本（语音模式）
3. **LLM 处理**：Llama 3.3 70B 理解用户意图，收集订单信息
4. **状态管理**：更新会话状态和订单草稿
5. **确认订单**：信息收集完整后，向用户复述确认
6. **保存订单**：用户确认后保存到数据库

### 进度查询流程（Function Calling）
1. **用户提问**："订单 #5 做好了吗？"
2. **意图识别**：LLM 判断需要调用 `get_order_status` 工具
3. **工具调用**：自动查询订单 #5 的实时进度
4. **生成回复**：LLM 根据工具返回的数据，用自然语言回答用户

## 🚀 快速开始

### 1. 环境要求

- Python 3.8+
- Node.js 16+ 和 npm/yarn/pnpm

### 2. 安装依赖

**后端依赖：**

```bash
# 克隆项目
git clone <repository_url>
cd AiAgentSystem

# 安装 Python 依赖
pip install -r requirements.txt
```

**前端依赖：**

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

### 3. 配置环境变量

复制 `.env.example` 为 `.env` 并填入你的 API Keys：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# AssemblyAI
ASSEMBLYAI_API_KEY=your_assemblyai_api_key_here

# OpenRouter（优先）
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct
OPENROUTER_SITE_URL=https://your-site-url.example.com
OPENROUTER_SITE_NAME=Tea Order Agent
ASSEMBLYAI_TTS_VOICE=alloy

# vLLM 备选（可选）
VLLM_BASE_URL=https://<modal-user>--vllm-llama70b-serve-vllm.modal.run/v1
VLLM_MODEL=meta-llama/Llama-3.1-70B-Instruct
VLLM_API_KEY=EMPTY  # 如在 vLLM 端设置 --api-key，则填入对应值
VLLM_GPU_COUNT=2
VLLM_TENSOR_PARALLEL=2

# 兼容 OpenAI（如需）
OPENAI_API_KEY=

# Database
DATABASE_PATH=./tea_orders.db

# Server
HOST=0.0.0.0
PORT=8000
```

**获取 / 配置说明：**
- AssemblyAI: https://www.assemblyai.com/
- OpenRouter: https://openrouter.ai/keys （申请 key 并确保账户余额足够，开启 Llama 3.3 70B 可用的 provider）
- vLLM 备选：部署 `modal_vllm.py` 到 Modal，拿到 URL 后设置 `VLLM_BASE_URL=https://.../v1`；如开启 `--api-key` 认证则同步配置 `VLLM_API_KEY`
- OpenAI: https://platform.openai.com/ （兼容用途，可留空）

### 4. 启动服务

**启动后端：**

```bash
# 在项目根目录
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**启动前端：**

```bash
# 在 frontend 目录
cd frontend
npm run dev
# 或
yarn dev
# 或
pnpm dev
```

服务启动后，访问：
- 前端页面：http://localhost:3000
- API 文档：http://localhost:8000/docs
- 进度查询：通过 `/text` 接口统一处理，Agent 自动调用工具
- 进度接口：`GET /orders/{order_id}/status` 查询制作阶段、ETA
- 排队面板接口：`GET /production/queue` / `ws://<host>/ws/production/queue`
- TTS 接口：`POST /tts` 调用 AssemblyAI 合成语音

### 5. 使用系统

#### 方式一：使用前端界面

1. 访问 http://localhost:3000
2. 选择"文字模式"或"语音模式"
3. 开始与 AI 接待员对话

**文字模式示例对话：**
```
用户：我要一杯乌龙奶茶
AI：好的！请问您想要什么杯型？我们有小杯、中杯、大杯。甜度和冰块呢？

用户：大杯，三分糖，去冰
AI：好的！为您确认一下：大杯乌龙奶茶，三分糖，去冰。请问需要加料吗？

用户：加珍珠
AI：好的！为您下单：大杯乌龙奶茶，三分糖，去冰，加珍珠。请问确认下单吗？

用户：确认
AI：好的，订单已确认！订单号：#1

### 统一 Agent 示例（点单 + 进度查询）

```
用户：我要一杯乌龙奶茶
AI：好的！请问您想要什么杯型？我们有小杯、中杯、大杯。

用户：大杯，三分糖，去冰，加珍珠
AI：好的！为您确认一下：大杯乌龙奶茶，三分糖，去冰，加珍珠。请问确认下单吗？

用户：确认
AI：好的，订单已确认！订单号：#12

用户：我的订单做好了吗？
AI：[调用 get_order_status(12) 工具]
    订单 #12 正在「制作中」阶段，预计还需 2 分钟完成。后续流程：封杯打包 → 可取餐。

用户：现在队伍排到哪了？
AI：[调用 get_all_orders_queue() 工具]
    目前有 5 个订单在制作中：#10 正在封杯、#11 制作中、#12 制作中...
```

#### 方式二：使用 API（测试/集成）

**文本输入接口：**

```bash
curl -X POST "http://localhost:8000/text" \
  -F "session_id=test_session_123" \
  -F "text=我要一杯大杯乌龙奶茶，三分糖，去冰"
```

**实时语音识别：**

通过 WebSocket 连接 `ws://localhost:8000/ws/stt` 进行实时语音识别，详见前端 VoiceInput 组件实现。

**查询订单：**

```bash
# 获取所有订单
curl http://localhost:8000/orders

# 获取特定订单
curl http://localhost:8000/orders/1
```

## 📁 项目结构

```
AiAgentSystem/
├── backend/                 # 后端 FastAPI 服务
│   ├── __init__.py
│   ├── main.py             # FastAPI 主程序
│   ├── models.py           # 数据模型定义
│   ├── config.py           # 配置文件
│   ├── database.py         # SQLite 数据库操作
│   ├── session_manager.py  # 会话状态管理
│   ├── stt.py             # AssemblyAI STT 集成
│   └── agent.py           # LLM Agent 点单逻辑
├── frontend/               # 前端 React + TypeScript
│   ├── src/
│   │   ├── components/    # React 组件
│   │   │   ├── ChatContainer.tsx
│   │   │   ├── Message.tsx
│   │   │   ├── ModeSelector.tsx
│   │   │   ├── OrderInfo.tsx
│   │   │   ├── TextInput.tsx
│   │   │   └── VoiceInput.tsx
│   │   ├── hooks/         # 自定义 Hooks
│   │   │   └── useAudioRecorder.ts
│   │   ├── services/      # API 服务
│   │   │   ├── api.ts
│   │   │   └── utils.ts
│   │   ├── types/         # TypeScript 类型定义
│   │   │   └── index.ts
│   │   ├── App.tsx        # 主应用组件
│   │   ├── main.tsx       # 入口文件
│   │   └── index.css      # 全局样式
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts     # Vite 配置
│   ├── tailwind.config.js # Tailwind 配置
│   └── tsconfig.json      # TypeScript 配置
├── .env.example           # 环境变量示例
├── .gitignore
├── requirements.txt       # Python 依赖
├── start.sh              # 启动脚本
├── test_api.sh           # API 测试脚本
└── README.md
```

## 🔧 核心模块说明

### 前端技术栈

**框架与工具：**
- ⚡ **Vite** - 快速的前端构建工具
- ⚛️ **React 18** - UI 框架
- 📘 **TypeScript** - 类型安全
- 🎨 **Tailwind CSS** - 实用优先的 CSS 框架
- 🎭 **Lucide React** - 图标库

**主要组件：**
- `App.tsx` - 主应用，管理整体状态和业务逻辑
- `ChatContainer.tsx` - 聊天消息容器
- `Message.tsx` - 单条消息展示
- `ModeSelector.tsx` - 输入模式切换
- `TextInput.tsx` - 文本输入组件
- `VoiceInput.tsx` - 语音录音组件
- `OrderInfo.tsx` - 订单信息展示

**自定义 Hooks：**
- `useAudioRecorder` - 音频录制功能封装

**API 服务：**
- `ApiService` - 封装所有后端 API 调用
- 类型安全的请求/响应处理

### 后端模块

### 1. Agent 模块 (`backend/agent.py`)

负责 LLM 对话逻辑：
- 构建 system prompt，定义 Agent 角色和行为
- 处理用户输入，更新订单状态
- 决定下一步动作（继续询问/确认/保存）

### 2. STT 模块 (`backend/stt.py`)

集成 AssemblyAI：
- 上传音频文件
- 异步等待转录结果
- 返回识别的文本

### 3. 数据库模块 (`backend/database.py`)

SQLite 操作：
- 订单表的创建和初始化
- 订单的保存和查询

### 4. 会话管理器 (`backend/session_manager.py`)

内存会话状态：
- 管理多个会话的对话历史
- 维护订单草稿
- 跟踪会话状态

## 📊 数据模型

### 订单状态 (OrderState)

```python
{
    "drink_name": "乌龙奶茶",      # 饮品名称
    "size": "大杯",                # 杯型
    "sugar": "三分糖",             # 甜度
    "ice": "去冰",                 # 冰块
    "toppings": ["珍珠"],          # 加料列表
    "notes": "不要太烫",           # 备注
    "is_complete": true            # 是否完整
}
```

### Agent 响应 (AgentResponse)

```python
{
    "assistant_reply": "好的，订单已确认！",
    "order_state": { ... },
    "action": "save_order"  # ask_more | confirm | save_order
}
```

## 🎯 菜单配置

当前系统内置的菜单（可在 `backend/models.py` 中修改）：

- 乌龙奶茶（¥15）
- 茉莉奶绿（¥15）
- 红茶拿铁（¥16）
- 抹茶拿铁（¥18）
- 黑糖珍珠奶茶（¥18）
- 芝士奶盖（¥20）

**配置选项：**
- 杯型：小杯、中杯、大杯
- 甜度：无糖、三分糖、五分糖、七分糖、全糖
- 冰块：去冰、少冰、正常冰、多冰
- 加料：珍珠、布丁、仙草、椰果、芋圆

## 🧪 测试

### 前端开发模式

前端支持热重载开发：

```bash
cd frontend
npm run dev
```

访问 http://localhost:3000 即可看到实时更新。

### 前端构建

```bash
cd frontend
npm run build
```

构建产物将生成在 `frontend/dist` 目录。

### 测试文本模式（不需要 AssemblyAI API Key）

```bash
# 启动后端服务
python -m uvicorn backend.main:app --reload

# 在另一个终端测试
curl -X POST "http://localhost:8000/text" \
  -F "session_id=test1" \
  -F "text=我要一杯奶茶"
```

### 测试完整流程

1. 设置好 API Keys
2. 启动后端和前端服务
3. 访问 http://localhost:3000
4. 选择"文字模式"进行完整点单流程
5. 测试"语音模式"（需要麦克风权限）

## 📝 API 文档

启动服务后访问 http://localhost:8000/docs 查看完整的 API 文档（Swagger UI）。

### 主要接口

| 接口 | 方法 | 说明 |
|-----|------|-----|
| `/ws/stt` | WebSocket | 实时语音识别 |
| `/text` | POST | 处理文本输入 |
| `/orders/{order_id}` | GET | 查询订单 |
| `/orders` | GET | 查询所有订单 |
| `/session/{session_id}` | GET | 查询会话状态 |
| `/reset/{session_id}` | POST | 重置会话 |

## 🔍 故障排除

### 前端问题

#### 1. CORS 错误

如果遇到跨域问题，确保：
- 后端 FastAPI 已配置 CORS（已在 `backend/main.py` 中配置）
- 前端 API 请求地址正确

#### 2. 前端无法连接后端

- 检查后端服务是否正常运行（http://localhost:8000）
- 检查 `frontend/src/services/api.ts` 中的 `API_BASE_URL`
- 可以设置环境变量 `VITE_API_URL`

#### 3. 语音录音不工作

- 确保浏览器支持 MediaRecorder API
- 检查麦克风权限
- 使用 HTTPS 或 localhost（某些浏览器限制）

### 后端问题

#### 1. 实时语音识别失败

- 检查 AssemblyAI API Key 是否正确
- 确认麦克风权限已授予
- 查看 AssemblyAI 账户余额
- 检查 WebSocket 连接是否正常

#### 2. OpenRouter API 调用失败

- 检查 OPENROUTER_API_KEY 是否正确
- 确认账户余额充足
- 验证模型 (meta-llama/llama-3.3-70b-instruct) 可用
- 检查网络连接

#### 3. 数据库错误

- 确保有写入权限
- 检查 `DATABASE_PATH` 配置

## 🚀 部署建议

### 生产环境优化

1. **使用 Redis 替代内存会话管理**：
   - 支持多实例部署
   - 会话持久化

2. **使用 PostgreSQL/MySQL 替代 SQLite**：
   - 更好的并发性能
   - 更强的数据完整性

3. **添加认证和授权**：
   - JWT 或 OAuth2
   - API 限流

4. **配置 HTTPS**：
   - 使用 Nginx/Caddy 反向代理
   - SSL 证书

5. **监控和日志**：
   - 集成 Sentry 错误追踪
   - 使用 ELK 收集日志

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📮 联系方式

如有问题或建议，请提交 Issue。
