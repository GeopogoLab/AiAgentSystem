#!/bin/bash

# 奶茶点单 AI Agent 系统启动脚本

echo "🧋 启动奶茶点单 AI Agent 系统..."

# 检查是否存在 .env 文件
if [ ! -f .env ]; then
    echo "⚠️  未找到 .env 文件"
    echo "📝 正在从 .env.example 创建 .env 文件..."
    cp .env.example .env
    echo "✅ 已创建 .env 文件，请编辑该文件并填入你的 API Keys"
    echo ""
    echo "需要配置："
    echo "  - ASSEMBLYAI_API_KEY: https://www.assemblyai.com/"
    echo "  - OPENAI_API_KEY: https://platform.openai.com/"
    echo ""
    read -p "按回车键继续（请确保已配置 API Keys）..."
fi

# 检查 Python 依赖
echo "📦 检查 Python 依赖..."
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "⚠️  缺少依赖包，正在安装..."
    pip install -r requirements.txt
fi

# 创建上传目录
mkdir -p uploads

# 启动服务
echo "🚀 启动后端服务..."
echo ""
echo "API 文档: http://localhost:8000/docs"
echo "前端页面: 请在浏览器中打开 frontend/index.html"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

python3 -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
