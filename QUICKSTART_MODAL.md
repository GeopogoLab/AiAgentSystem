# 🚀 快速部署到 Modal.com

5 分钟内将茶饮点单系统部署到云端！

## 第一步：安装 Modal

```bash
pip install modal
```

## 第二步：登录 Modal

```bash
modal token new
```

这会打开浏览器完成认证。

## 第三步：创建 Secret

1. 访问 https://modal.com/secrets
2. 点击 **Create Secret**
3. 名称填写：`tea-agent-secrets`
4. 添加环境变量：

```
ASSEMBLYAI_API_KEY=你的AssemblyAI密钥
OPENROUTER_API_KEY=你的OpenRouter密钥
```

## 第四步：一键部署

### 方式 1：使用部署脚本（推荐）

```bash
./deploy.sh
```

### 方式 2：手动部署

```bash
modal deploy modal_app.py
```

### 额外：部署 vLLM 70B 备选（OpenRouter 降级用）

```bash
./deploy_vllm.sh
# 或
modal deploy modal_vllm.py
```

部署完成后，将返回的 URL（形如 `https://<你>--vllm-llama70b-serve-vllm.modal.run/v1`）填入 `.env` 的 `VLLM_BASE_URL`。默认请求 2×A100-80G，如需下调请同步调节 `VLLM_GPU_COUNT` / `VLLM_TENSOR_PARALLEL`。

## 第五步：获取 URL

部署成功后，你会看到类似这样的输出：

```
✓ Created web function fastapi_app => https://your-username--tea-order-agent-fastapi-app.modal.run
```

**复制这个 URL！**

## 第六步：配置前端

在 `frontend/.env` 文件中添加：

```env
VITE_API_URL=https://your-username--tea-order-agent-fastapi-app.modal.run
```

## 完成！🎉

现在访问前端应用，它会自动连接到 Modal 上的后端。

---

## 常用命令

### 查看日志
```bash
modal app logs tea-order-agent --follow
```

### 查看应用列表
```bash
modal app list
```

### 停止应用
```bash
modal app stop tea-order-agent
```

### 更新代码
修改代码后重新部署：
```bash
modal deploy modal_app.py
```

---

## 故障排除

### ❌ "Secret not found"
确保在 Modal 控制台创建了名为 `tea-agent-secrets` 的 Secret。

### ❌ "Authentication failed"
运行 `modal token new` 重新登录。

### ❌ CORS 错误
后端已配置允许所有来源，检查前端的 API URL 是否正确。

---

## 需要帮助？

查看详细部署指南：[MODAL_DEPLOYMENT.md](./MODAL_DEPLOYMENT.md)

Modal 官方文档：https://modal.com/docs
