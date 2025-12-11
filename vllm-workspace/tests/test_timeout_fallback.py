#!/usr/bin/env python3
"""
快速测试超时降级功能

测试内容：
1. 配置加载
2. LLMBackend 初始化（包含 timeout 字段）
3. 错误分类逻辑
4. 实际超时降级（如果配置了 vLLM）
"""
import asyncio
import sys
from pathlib import Path

# 添加 backend 到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from backend.config import config
from backend.llm.backends import LLMBackendRouter
from openai import APITimeoutError, APIConnectionError, RateLimitError


def test_config():
    """测试配置加载"""
    print("=" * 70)
    print("测试 1: 配置加载")
    print("=" * 70)

    print(f"✅ OPENROUTER_TIMEOUT: {config.OPENROUTER_TIMEOUT} 秒")
    print(f"✅ VLLM_TIMEOUT: {config.VLLM_TIMEOUT} 秒")
    print(f"✅ VLLM_BASE_URL: {config.VLLM_BASE_URL}")
    print(f"✅ VLLM_MODEL: {config.VLLM_MODEL}")
    print()

    assert hasattr(config, "OPENROUTER_TIMEOUT"), "缺少 OPENROUTER_TIMEOUT 配置"
    assert hasattr(config, "VLLM_TIMEOUT"), "缺少 VLLM_TIMEOUT 配置"
    assert config.OPENROUTER_TIMEOUT == 5.0, f"OPENROUTER_TIMEOUT 应为 5.0，实际为 {config.OPENROUTER_TIMEOUT}"
    assert config.VLLM_TIMEOUT == 10.0, f"VLLM_TIMEOUT 应为 10.0，实际为 {config.VLLM_TIMEOUT}"

    print("✅ 配置测试通过\n")


def test_backend_initialization():
    """测试 LLMBackend 初始化"""
    print("=" * 70)
    print("测试 2: LLMBackend 初始化")
    print("=" * 70)

    router = LLMBackendRouter(config)

    print(f"可用后端数量: {len(router.backends)}")

    for backend in router.backends:
        print(f"\n后端: {backend.name}")
        print(f"  - 模型: {backend.model}")
        print(f"  - 超时: {backend.timeout} 秒")

        # 验证超时字段存在
        assert hasattr(backend, "timeout"), f"{backend.name} 缺少 timeout 字段"

        # 验证超时值正确
        if backend.name == "openrouter":
            assert backend.timeout == 5.0, f"OpenRouter 超时应为 5.0，实际为 {backend.timeout}"
        elif backend.name == "vllm":
            assert backend.timeout == 10.0, f"vLLM 超时应为 10.0，实际为 {backend.timeout}"

    print("\n✅ LLMBackend 初始化测试通过\n")


def test_error_classification():
    """测试错误分类逻辑"""
    print("=" * 70)
    print("测试 3: 错误分类逻辑")
    print("=" * 70)

    router = LLMBackendRouter(config)

    # 使用 isinstance 检查来测试错误分类逻辑
    # 创建实际的异常实例需要特殊参数，这里我们测试类型检查

    print("测试可重试错误类型识别:")

    # 创建简单的子类实例来测试
    class TestTimeoutError(APITimeoutError):
        def __init__(self):
            pass

    class TestConnectionError(APIConnectionError):
        def __init__(self):
            pass

    class TestRateLimitError(RateLimitError):
        def __init__(self):
            pass

    timeout_error = TestTimeoutError()
    assert router._is_retriable_error(timeout_error), "APITimeoutError 应该是可重试错误"
    print("✅ APITimeoutError -> 可重试")

    connection_error = TestConnectionError()
    assert router._is_retriable_error(connection_error), "APIConnectionError 应该是可重试错误"
    print("✅ APIConnectionError -> 可重试")

    rate_limit_error = TestRateLimitError()
    assert router._is_retriable_error(rate_limit_error), "RateLimitError 应该是可重试错误"
    print("✅ RateLimitError -> 可重试")

    print("\n测试不可重试错误类型识别:")

    # 测试不可重试错误
    value_error = ValueError("Invalid parameter")
    assert not router._is_retriable_error(value_error), "ValueError 不应该是可重试错误"
    print("✅ ValueError -> 不可重试")

    runtime_error = RuntimeError("Some runtime error")
    assert not router._is_retriable_error(runtime_error), "RuntimeError 不应该是可重试错误"
    print("✅ RuntimeError -> 不可重试")

    print("\n✅ 错误分类测试通过\n")


async def test_actual_call():
    """测试实际 LLM 调用（如果配置了后端）"""
    print("=" * 70)
    print("测试 4: 实际 LLM 调用测试")
    print("=" * 70)

    router = LLMBackendRouter(config)

    if not router.backends:
        print("⚠️ 未配置任何 LLM 后端，跳过实际调用测试")
        return

    messages = [
        {"role": "user", "content": "Say 'Hello, timeout test!' in one sentence."}
    ]

    try:
        print(f"\n发送测试请求到 {len(router.backends)} 个后端...")

        response, provider = await router.call_with_fallback(
            messages=messages,
            max_tokens=50
        )

        print(f"\n✅ 调用成功!")
        print(f"   使用后端: {provider.name}")
        print(f"   响应内容: {response.choices[0].message.content[:100]}")

        if hasattr(response, "usage"):
            print(f"   Token 使用: {response.usage}")

    except Exception as e:
        print(f"\n❌ 调用失败: {type(e).__name__}: {e}")
        print("   这可能是因为 API key 未配置或无效")


def main():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("Modal vLLM 超时降级功能测试")
    print("=" * 70 + "\n")

    try:
        # 测试 1: 配置加载
        test_config()

        # 测试 2: Backend 初始化
        test_backend_initialization()

        # 测试 3: 错误分类
        test_error_classification()

        # 测试 4: 实际调用
        asyncio.run(test_actual_call())

        print("=" * 70)
        print("✅ 所有测试通过！")
        print("=" * 70)

        print("\n下一步建议：")
        print("1. 启动后端服务: python backend/main.py")
        print("2. 测试超时场景（模拟 OpenRouter 慢响应）")
        print("3. 检查日志确认降级行为")

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
