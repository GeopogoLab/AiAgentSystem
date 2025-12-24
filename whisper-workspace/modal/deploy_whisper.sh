#!/bin/bash
# Whisper STT Modal 部署脚本

set -e  # 遇到错误立即退出

echo "========================================"
echo "Whisper STT Modal 部署"
echo "========================================"

# 检查 Modal CLI 是否安装
if ! command -v modal &> /dev/null; then
    echo "❌ Modal CLI 未安装"
    echo ""
    echo "请先安装 Modal CLI:"
    echo "  pip install modal"
    echo ""
    exit 1
fi

echo "✅ Modal CLI 已安装 ($(modal --version | head -1))"
echo ""

# 检查 Modal 是否已登录（通过尝试列出 apps）
if ! modal app list &> /dev/null; then
    echo "❌ Modal 未登录"
    echo ""
    echo "请先登录 Modal（选择其中一种方式）:"
    echo ""
    echo "方式 1: 浏览器登录（推荐）"
    echo "  modal token new"
    echo ""
    echo "方式 2: 使用现有 token"
    echo "  modal token set --token-id ak-xxx --token-secret as-xxx"
    echo ""
    echo "获取 token: https://modal.com/settings"
    echo ""
    exit 1
fi

echo "✅ Modal 已登录"
echo ""

# 部署服务
echo "📦 部署 Whisper STT 服务..."
cd "$(dirname "$0")"

modal deploy modal_whisper_stt.py

echo ""
echo "========================================"
echo "✅ 部署完成！"
echo "========================================"
echo ""
echo "接下来的步骤:"
echo ""
echo "1. 获取你的 Modal 用户名:"
echo "   modal profile current"
echo ""
echo "2. 将以下内容添加到 .env 文件:"
echo "   WHISPER_SERVICE_URL=wss://<your-username>--whisper-stt-wrapper.modal.run/ws/stt"
echo ""
echo "3. 测试服务（替换 <your-username>）:"
echo "   curl https://<your-username>--whisper-stt-wrapper.modal.run/health"
echo ""
echo "4. 查看日志:"
echo "   modal app logs whisper-stt"
echo ""
echo "5. 重启主后端:"
echo "   cd ../../backend && ./start.sh"
echo ""
