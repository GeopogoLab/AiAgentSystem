# vLLM Workspace

集中管理 vLLM 相关操作（部署、测试、配置），避免文件散落。

## 目标
- 单独存放 vLLM 配置样例与操作指令
- 依赖现有的 `modal_vllm.py` / `deploy_vllm.sh` / `VLLM_MODAL_DEPLOYMENT.md`
- 不存放任何真实密钥

## 快速部署到 Modal
1. 准备 Secret（必须有 HF Token 且已同意模型协议）：
   ```bash
   modal secret create vllm-secrets \
     HUGGING_FACE_HUB_TOKEN=hf_xxx \
     VLLM_SERVER_API_KEY=your-key   # 可选
   ```
2. 选择模型并部署（示例：DeepSeek）：
   ```bash
   VLLM_MODEL="deepseek-ai/DeepSeek-V3.2-Exp" modal deploy modal_vllm.py
   ```
3. 验证：
   ```bash
   BASE="https://<workspace>--vllm-llama70b-serve-vllm.modal.run/v1"
   curl -H "Authorization: Bearer <VLLM_SERVER_API_KEY或EMPTY>" "$BASE/models"
   ```

## 接入后端降级链路
在 `.env` 写入：
```env
VLLM_BASE_URL=https://<workspace>--vllm-llama70b-serve-vllm.modal.run/v1
VLLM_API_KEY=<与 VLLM_SERVER_API_KEY 一致或 EMPTY>
VLLM_MODEL=deepseek-ai/DeepSeek-V3.2-Exp
```
后端自动按 OpenRouter → vLLM 备选降级。

## 本地验证（非 Modal）
```bash
pip install vllm
vllm serve "deepseek-ai/DeepSeek-V3.2-Exp"
curl http://localhost:8000/v1/models
```

## 参考文件
- `modal_vllm.py`：Modal 服务定义
- `deploy_vllm.sh`：自动化部署脚本
- `VLLM_MODAL_DEPLOYMENT.md`：完整操作指南
- `.env.vllm.example`：vLLM 相关环境变量样例
