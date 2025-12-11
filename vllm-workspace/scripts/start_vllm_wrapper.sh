#!/bin/bash
# 启动 VLLM Wrapper 服务
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# 导出环境变量
export VLLM_BASE_URL=https://ybpang-1--vllm-llama70b-serve-vllm.modal.run/v1
export VLLM_MODEL=meta-llama/Llama-3.1-70B-Instruct
export VLLM_API_KEY=<your-vllm-api-key>
export VLLM_WRAPPER_PORT=8001

echo "🚀 启动 VLLM Wrapper 服务"
echo "================================"
echo "VLLM Base URL: $VLLM_BASE_URL"
echo "Model: $VLLM_MODEL"
echo "Port: $VLLM_WRAPPER_PORT"
echo ""

export PYTHONPATH="$ROOT_DIR/tools:$PYTHONPATH"
python -m uvicorn vllm_wrapper:app --host 0.0.0.0 --port $VLLM_WRAPPER_PORT
