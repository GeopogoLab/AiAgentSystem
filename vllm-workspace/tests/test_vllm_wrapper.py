"""
测试 VLLM Wrapper 服务
"""
import asyncio
import httpx
import os


async def test_health():
    """测试健康检查"""
    print("=" * 60)
    print("测试 1: 健康检查")
    print("=" * 60)

    url = "http://localhost:8001/health"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            print(f"状态码: {response.status_code}")
            print(f"响应: {response.json()}")
        except Exception as e:
            print(f"❌ 健康检查失败: {e}")

    print()


async def test_models():
    """测试模型列表"""
    print("=" * 60)
    print("测试 2: 列出模型")
    print("=" * 60)

    url = "http://localhost:8001/models"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30.0)
            print(f"状态码: {response.status_code}")
            print(f"响应: {response.json()}")
        except Exception as e:
            print(f"❌ 获取模型列表失败: {e}")

    print()


async def test_chat():
    """测试对话接口（非流式）"""
    print("=" * 60)
    print("测试 3: 对话接口（非流式）")
    print("=" * 60)

    url = "http://localhost:8001/chat"
    headers = {"Content-Type": "application/json"}

    # 如果设置了API key，添加认证
    api_key = os.getenv("VLLM_WRAPPER_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "messages": [
            {"role": "system", "content": "你是一个有帮助的AI助手，回答要简洁。"},
            {"role": "user", "content": "用一句话介绍什么是机器学习"}
        ],
        "max_tokens": 200,
        "temperature": 0.7
    }

    async with httpx.AsyncClient() as client:
        try:
            print(f"发送请求到: {url}")
            print(f"消息: {payload['messages'][-1]['content']}")
            print("\n等待VLLM响应...")

            response = await client.post(url, json=payload, headers=headers, timeout=60.0)

            print(f"\n状态码: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print(f"✅ 对话成功!")
                print(f"\n回复内容:\n{result['content']}")
                print(f"\n使用的模型: {result['model']}")
                if result.get('usage'):
                    print(f"Token使用: {result['usage']}")
            else:
                print(f"❌ 请求失败: {response.text}")

        except httpx.TimeoutException:
            print("❌ 请求超时 - VLLM可能正在冷启动，请等待几分钟后重试")
        except Exception as e:
            print(f"❌ 对话请求失败: {e}")

    print()


async def test_chat_stream():
    """测试对话接口（流式）"""
    print("=" * 60)
    print("测试 4: 对话接口（流式）")
    print("=" * 60)

    url = "http://localhost:8001/chat"
    headers = {"Content-Type": "application/json"}

    # 如果设置了API key，添加认证
    api_key = os.getenv("VLLM_WRAPPER_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "messages": [
            {"role": "user", "content": "用两句话解释什么是深度学习"}
        ],
        "stream": True,
        "max_tokens": 200,
        "temperature": 0.7
    }

    async with httpx.AsyncClient() as client:
        try:
            print(f"发送流式请求到: {url}")
            print(f"消息: {payload['messages'][-1]['content']}")
            print("\n流式响应:\n")

            async with client.stream("POST", url, json=payload, headers=headers, timeout=60.0) as response:
                if response.status_code != 200:
                    print(f"❌ 请求失败: {response.status_code}")
                    return

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        content = line[6:]  # 去掉 "data: " 前缀
                        if content == "[DONE]":
                            print("\n\n✅ 流式响应完成!")
                            break
                        elif content.startswith("[ERROR]"):
                            print(f"\n❌ 错误: {content}")
                            break
                        else:
                            print(content, end="", flush=True)

        except httpx.TimeoutException:
            print("\n❌ 请求超时 - VLLM可能正在冷启动，请等待几分钟后重试")
        except Exception as e:
            print(f"\n❌ 流式对话失败: {e}")

    print()


async def main():
    """运行所有测试"""
    print("\n🧪 VLLM Wrapper 服务测试")
    print("=" * 60)
    print(f"目标地址: http://localhost:8001")
    print(f"VLLM后端: {os.getenv('VLLM_BASE_URL', '未设置')}")
    print()

    # 运行测试
    await test_health()

    # 询问是否继续
    print("健康检查完成。如果VLLM可用，我们将继续测试其他接口。")
    print("按 Enter 继续，或 Ctrl+C 取消...")
    # input()  # 注释掉，自动继续

    await test_models()
    await test_chat()
    await test_chat_stream()

    print("=" * 60)
    print("✅ 所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
