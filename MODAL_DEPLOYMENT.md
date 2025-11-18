# Modal.com 部署指南

本指南将帮助您将茶饮点单系统后端部署到 Modal.com。

## 前置要求

1. **注册 Modal 账号**
   - 访问 https://modal.com
   - 注册并登录账号

2. **安装 Modal CLI**
   ```bash
   pip install modal
   ```

3. **登录 Modal**
   ```bash
   modal token new
   ```
   - 这将打开浏览器完成认证

## 部署步骤

### 1. 配置环境变量（Secrets）

在 Modal 控制台创建 Secret：

1. 访问 https://modal.com/secrets
2. 点击 "Create Secret"
3. 名称设置为：`tea-agent-secrets`
4. 添加以下环境变量：

   **必需的环境变量：**
   ```
   ASSEMBLYAI_API_KEY=your_assemblyai_api_key_here
   OPENROUTER_API_KEY=your_openrouter_api_key_here
   ```

   **可选的环境变量：**
   ```
   OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct
   OPENROUTER_SITE_URL=https://yoursite.com
   OPENROUTER_SITE_NAME=Tea Order Agent
   ASSEMBLYAI_TTS_VOICE=alloy
   OPENAI_TEMPERATURE=0.7
   ```

### 2. 部署应用

在项目根目录执行：

```bash
modal deploy modal_app.py
```

部署成功后，您会看到类似这样的输出：
```
✓ Created web function fastapi_app => https://your-username--tea-order-agent-fastapi-app.modal.run
```

### 3. 获取应用 URL

部署完成后，Modal 会提供一个 HTTPS URL，格式类似：
```
https://your-username--tea-order-agent-fastapi-app.modal.run
```

将此 URL 记录下来，用于前端配置。

### 4. 配置前端

在前端项目中，更新 API URL：

**方法 1：环境变量（推荐）**

在 `frontend/.env` 文件中设置：
```env
VITE_API_URL=https://your-username--tea-order-agent-fastapi-app.modal.run
```

**方法 2：直接修改代码**

在前端代码中找到 API 配置，将 URL 更新为 Modal 提供的 URL。

### 5. 测试部署

访问 Modal 提供的 URL：
```
https://your-username--tea-order-agent-fastapi-app.modal.run/
```

您应该看到 API 欢迎信息。

测试健康检查：
```
https://your-username--tea-order-agent-fastapi-app.modal.run/health
```

## 常用命令

### 查看应用列表
```bash
modal app list
```

### 查看应用日志
```bash
modal app logs tea-order-agent
```

### 查看实时日志（跟踪模式）
```bash
modal app logs tea-order-agent --follow
```

### 停止应用
```bash
modal app stop tea-order-agent
```

### 删除应用
```bash
modal app delete tea-order-agent
```

### 重新部署（更新代码后）
```bash
modal deploy modal_app.py
```

## 数据持久化

- 数据库文件存储在 Modal Volume 中，路径为 `/data/tea_orders.db`
- 即使应用重启，数据也会保留
- Volume 名称：`tea-orders-db`

### 查看 Volume
```bash
modal volume list
```

### 下载数据库备份
```bash
modal volume get tea-orders-db tea_orders.db
```

## 性能配置

当前配置：
- **并发请求数**：100
- **容器超时**：1 小时
- **空闲超时**：5 分钟

如需调整，编辑 `modal_app.py` 中的 `@app.function` 装饰器参数：

```python
@app.function(
    timeout=3600,  # 调整超时时间
    container_idle_timeout=300,  # 调整空闲超时
    allow_concurrent_inputs=100,  # 调整并发数
)
```

## 成本估算

Modal 提供免费额度，超出后按使用量计费：
- **免费额度**：每月 $30 免费额度
- **计费方式**：按 CPU/内存使用时间计费
- **空闲优化**：容器空闲 5 分钟后自动休眠，节省成本

查看详细价格：https://modal.com/pricing

## 故障排除

### 1. 部署失败

检查错误信息：
```bash
modal deploy modal_app.py --verbose
```

### 2. Secret 未找到错误

确保在 Modal 控制台创建了名为 `tea-agent-secrets` 的 Secret。

### 3. 数据库错误

检查 Volume 是否正确挂载：
```bash
modal volume list
```

### 4. API 请求失败

查看实时日志：
```bash
modal app logs tea-order-agent --follow
```

### 5. WebSocket 连接问题

Modal 支持 WebSocket，但确保：
- URL 使用正确的协议（wss:// 而非 ws://）
- 前端正确配置了 WebSocket 端点

## CORS 配置

如果遇到跨域问题，后端已配置允许所有来源：
```python
allow_origins=["*"]
```

生产环境建议限制为特定域名。

## 监控和日志

### 实时监控
访问 Modal Dashboard：https://modal.com/apps

### 查看指标
- 请求数
- 响应时间
- 错误率
- CPU/内存使用

### 告警设置
可在 Modal 控制台配置告警通知。

## 更新应用

代码修改后，重新部署：
```bash
modal deploy modal_app.py
```

Modal 会自动进行零停机部署（zero-downtime deployment）。

## 安全建议

1. ✅ 使用 Modal Secrets 管理 API Keys
2. ✅ 限制 CORS 允许的来源
3. ✅ 定期备份数据库
4. ✅ 监控异常请求
5. ✅ 设置合理的超时时间

## 支持

- Modal 文档：https://modal.com/docs
- Modal Discord：https://discord.gg/modal
- Modal GitHub：https://github.com/modal-labs/modal-examples

---

部署完成！🎉

现在您的茶饮点单系统后端已经运行在 Modal.com 上了。
