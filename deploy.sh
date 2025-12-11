#!/bin/bash

# Tea Order Agent - Modal 部署脚本
# 使用方法: ./deploy.sh

set -e  # 遇到错误立即退出

echo "🚀 Tea Order Agent - Modal 部署工具"
echo "===================================="
echo ""

# 检查 modal 是否已安装
if ! command -v modal &> /dev/null; then
    echo "❌ Modal CLI 未安装"
    echo "正在安装 Modal..."
    pip install modal
    echo "✅ Modal CLI 安装完成"
fi

# 检查是否已登录
echo "📋 检查 Modal 认证状态..."
if ! modal token current &> /dev/null; then
    echo "⚠️  未登录 Modal"
    echo "请运行以下命令登录："
    echo "  modal token new"
    echo ""
    read -p "是否现在登录? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        modal token new
    else
        echo "❌ 部署已取消"
        exit 1
    fi
fi

echo "✅ Modal 认证通过"
echo ""

# 检查 Secret 是否存在
echo "🔐 检查 Secret 配置..."
if ! modal secret list | grep -q "tea-agent-secrets"; then
    echo "⚠️  未找到 'tea-agent-secrets' Secret"
    echo ""
    echo "请先在 Modal 控制台创建 Secret："
    echo "  1. 访问: https://modal.com/secrets"
    echo "  2. 创建名为 'tea-agent-secrets' 的 Secret"
    echo "  3. 添加以下环境变量:"
    echo "     - ASSEMBLYAI_API_KEY"
    echo "     - OPENROUTER_API_KEY"
    echo ""
    read -p "Secret 已创建? 按回车继续部署..."
fi

echo "✅ Secret 配置检查完成"
echo ""

# 部署应用
echo "🚀 开始部署到 Modal..."
echo ""

modal deploy modal_app.py

echo ""
echo "✅ 部署成功！"
echo ""
echo "📊 查看应用状态:"
echo "  modal app list"
echo ""
echo "📝 查看日志:"
echo "  modal app logs tea-order-agent"
echo ""
echo "🔄 实时日志:"
echo "  modal app logs tea-order-agent --follow"
echo ""
echo "🌐 您的 API URL 已显示在上方部署输出中"
echo "   请将其配置到前端的 VITE_API_URL 环境变量"
echo ""
echo "💡 如果需要 OpenRouter 容灾，运行 ./deploy_vllm.sh 并在 .env 设置 VLLM_BASE_URL=https://<vllm-url>/v1"
echo ""
echo "🎉 部署完成！"
