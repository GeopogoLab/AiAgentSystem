#!/bin/bash
# 更新 VLLM Modal Secret
# 使用方法: ./update_vllm_secret.sh

echo "🔧 更新 VLLM Modal Secret"
echo "================================"
echo ""
echo "请输入你的 Hugging Face Token (hf_...):"
read -s HF_TOKEN

echo ""
echo "请输入你的 VLLM API Key (用于保护API端点，可选):"
read -s VLLM_API_KEY

if [ -z "$VLLM_API_KEY" ]; then
    VLLM_API_KEY="modal-vllm-key-$(date +%s)"
    echo "使用自动生成的 API Key: $VLLM_API_KEY"
fi

echo ""
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "正在更新 Modal Secret..."

# 删除旧secret
modal secret delete vllm-secrets 2>/dev/null

# 创建新secret
modal secret create vllm-secrets \
  HUGGING_FACE_HUB_TOKEN="$HF_TOKEN" \
  VLLM_SERVER_API_KEY="$VLLM_API_KEY"

echo ""
echo "✅ Secret 更新完成!"
echo ""
echo "请更新你的 .env 文件:"
echo "VLLM_API_KEY=$VLLM_API_KEY"
echo ""
echo "现在可以重新部署 VLLM:"
echo "modal deploy \"$ROOT_DIR/modal/modal_vllm.py\""
