#!/bin/bash

# vLLM 70B 备选服务部署脚本
# 用法: ./deploy_vllm.sh

set -e

echo "🚀 部署 vLLM 70B 到 Modal (OpenRouter 备选)"
echo "==========================================="

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# 检查 modal 是否已安装
if ! command -v modal &> /dev/null; then
    echo "❌ Modal CLI 未安装，正在安装..."
    pip install modal
fi

# 登录检查（modal 1.1+ 已无 token current 命令，用 profile list 验证）
echo "📋 检查 Modal 认证..."
if ! modal profile list &> /dev/null; then
    echo "⚠️  Modal 未登录或网络异常，请先运行: modal token new"
    exit 1
fi

# Secret 检查
echo "🔐 检查 Secret: vllm-secrets ..."
if ! modal secret list | grep -q "vllm-secrets"; then
    echo "⚠️  缺少 vllm-secrets，需包含至少 HUGGING_FACE_HUB_TOKEN（或 HF_TOKEN），如需鉴权可加 VLLM_SERVER_API_KEY"
    echo "    创建: https://modal.com/secrets"
    read -p "Secret 已创建后按 Enter 继续..."
fi

echo "✅ 环境检查通过，开始部署 vLLM ..."
modal deploy "$ROOT_DIR/modal/modal_vllm.py"

echo ""
echo "✅ vLLM 部署完成"
echo "👉 将 Modal 返回的 URL（形如 https://<你>-vllm-llama70b-serve-vllm.modal.run）"
echo "   配置到 VLLM_BASE_URL 环境变量（记得带 /v1 前缀）以启用后端自动回退。"
