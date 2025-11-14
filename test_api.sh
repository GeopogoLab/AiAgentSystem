#!/bin/bash

# API 测试脚本

BASE_URL="http://localhost:8000"
SESSION_ID="test_session_$(date +%s)"

echo "🧪 测试奶茶点单 AI Agent 系统"
echo "会话 ID: $SESSION_ID"
echo ""

# 测试 1: 健康检查
echo "1️⃣  测试健康检查..."
curl -s "$BASE_URL/health" | python3 -m json.tool
echo ""

# 测试 2: 查看根路径
echo "2️⃣  测试根路径..."
curl -s "$BASE_URL/" | python3 -m json.tool
echo ""

# 测试 3: 发送文本消息
echo "3️⃣  测试文本输入 - 第一轮..."
curl -s -X POST "$BASE_URL/text" \
  -F "session_id=$SESSION_ID" \
  -F "text=我要一杯乌龙奶茶" | python3 -m json.tool
echo ""

read -p "按回车继续下一轮对话..."

echo "4️⃣  测试文本输入 - 第二轮..."
curl -s -X POST "$BASE_URL/text" \
  -F "session_id=$SESSION_ID" \
  -F "text=大杯，三分糖，去冰" | python3 -m json.tool
echo ""

read -p "按回车继续下一轮对话..."

echo "5️⃣  测试文本输入 - 第三轮（加料）..."
curl -s -X POST "$BASE_URL/text" \
  -F "session_id=$SESSION_ID" \
  -F "text=加珍珠" | python3 -m json.tool
echo ""

read -p "按回车确认订单..."

echo "6️⃣  测试文本输入 - 确认订单..."
curl -s -X POST "$BASE_URL/text" \
  -F "session_id=$SESSION_ID" \
  -F "text=确认" | python3 -m json.tool
echo ""

# 测试 4: 查看会话状态
echo "7️⃣  查看会话状态..."
curl -s "$BASE_URL/session/$SESSION_ID" | python3 -m json.tool
echo ""

# 测试 5: 查看所有订单
echo "8️⃣  查看所有订单..."
curl -s "$BASE_URL/orders" | python3 -m json.tool
echo ""

# 测试 6: 重置会话
echo "9️⃣  重置会话..."
curl -s -X POST "$BASE_URL/reset/$SESSION_ID" | python3 -m json.tool
echo ""

echo "✅ 测试完成！"
