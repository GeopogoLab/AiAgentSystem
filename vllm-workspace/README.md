# vLLM Workspace

集中管理 vLLM 相关配置、部署脚本与文档，所有操作集中在 `vllm-workspace/` 目录之下。

## 目录结构
- `modal/`：Modal 服务定义脚本（`modal_vllm.py` 系列），包含不同模型/部署策略。
- `scripts/`：辅助脚本（部署、Secret 更新、Wrapper 启动），会自动定位到 `modal/` 和 `tools/`。
- `tools/`：vLLM Wrapper 服务源码（`vllm_wrapper.py`）及其他可复用工具。
- `tests/`：辅助测试脚本（如 `test_vllm_wrapper.py`、`test_timeout_fallback.py`）。
- `docs/`：迁移过来的部署/调优文档（如 `VLLM_MODAL_DEPLOYMENT.md`、`MODAL_VLLM_FALLBACK_IMPLEMENTATION.md`）。

## 快速部署到 Modal
1. 进入工作区：
   ```bash
   cd vllm-workspace
   ```
2. 创建 Secret：
   ```bash
   modal secret create vllm-secrets \
     HUGGING_FACE_HUB_TOKEN=hf_xxx \
     VLLM_SERVER_API_KEY=your-key
   ```
3. 手动部署：
   ```bash
   VLLM_MODEL="deepseek-ai/DeepSeek-V3.2-Exp" modal deploy modal/modal_vllm.py
   ```
   或使用脚本：
   ```bash
   ./scripts/deploy_vllm.sh
   ```
4. 验证模型列表：
   ```bash
   BASE="https://<workspace>--vllm-llama70b-serve-vllm.modal.run/v1"
   curl -H "Authorization: Bearer <VLLM_SERVER_API_KEY或EMPTY>" "$BASE/models"
   ```

## 接入点与本地验证
- 在 `.env` 中填入：
  ```env
  VLLM_BASE_URL=https://<workspace>--vllm-llama70b-serve-vllm.modal.run/v1
  VLLM_API_KEY=<与 VLLM_SERVER_API_KEY 一致或 EMPTY>
  VLLM_MODEL=deepseek-ai/DeepSeek-V3.2-Exp
  ```
- 本地启动 Wrapper：
  ```bash
  ./scripts/start_vllm_wrapper.sh
  ```

## 参考文档
- `docs/VLLM_MODAL_DEPLOYMENT.md`：完整 Modal 部署步骤
- `docs/MODAL_VLLM_FALLBACK_IMPLEMENTATION.md`：降级策略与实现细节
- `docs/VLLM_WRAPPER_GUIDE.md`：Wrapper 服务说明
