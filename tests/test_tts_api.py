"""测试 TTS API 服务的客户端

使用方式:
    python3 test_tts_api.py
"""

import base64
import requests
from pathlib import Path

# TTS 服务地址
TTS_URL = "http://localhost:8002"


def test_health():
    """测试健康检查"""
    print("\n1️⃣  测试健康检查...")
    response = requests.get(f"{TTS_URL}/health")
    print(f"   状态码: {response.status_code}")
    print(f"   响应: {response.json()}")
    return response.status_code == 200


def test_models():
    """测试模型列表"""
    print("\n2️⃣  测试模型列表...")
    response = requests.get(f"{TTS_URL}/models")
    print(f"   状态码: {response.status_code}")
    data = response.json()
    print(f"   当前模型: {data['current_model']}")
    print(f"   可用模型数: {len(data['available_models'])}")
    return response.status_code == 200


def test_tts(text: str, output_file: str = "api_test_output.wav"):
    """测试 TTS 合成"""
    print(f"\n3️⃣  测试 TTS 合成...")
    print(f"   文本: {text}")

    # 发送请求
    response = requests.post(
        f"{TTS_URL}/tts",
        json={
            "text": text,
            "voice": None,
            "format": "wav"
        },
        timeout=120  # TTS 可能需要一些时间
    )

    print(f"   状态码: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"   说话人: {data['voice']}")
        print(f"   格式: {data['format']}")
        print(f"   时长: {data['duration_sec']:.2f} 秒")

        # 解码并保存音频
        audio_bytes = base64.b64decode(data['audio_base64'])
        output_path = Path(output_file)
        output_path.write_bytes(audio_bytes)

        print(f"   ✅ 音频已保存到: {output_path.absolute()}")
        print(f"   文件大小: {len(audio_bytes) / 1024 / 1024:.2f} MB")

        return True
    else:
        print(f"   ❌ 错误: {response.text}")
        return False


def main():
    """运行所有测试"""
    print("=" * 60)
    print("🧪 TTS API 测试")
    print("=" * 60)

    # 测试健康检查
    try:
        if not test_health():
            print("\n❌ 健康检查失败，请确保 TTS 服务正在运行")
            print("   启动命令: python3 tts_service.py")
            return
    except requests.exceptions.ConnectionError:
        print("\n❌ 无法连接到 TTS 服务")
        print("   请先启动服务: python3 tts_service.py")
        return

    # 测试模型列表
    test_models()

    # 测试 TTS 合成
    test_texts = [
        "Hello, this is a test of the text to speech API.",
        "The quick brown fox jumps over the lazy dog.",
    ]

    for i, text in enumerate(test_texts, 1):
        success = test_tts(text, f"api_test_{i}.wav")
        if not success:
            print(f"\n❌ 测试 {i} 失败")
            return

    print("\n" + "=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60)
    print("\n播放音频:")
    print("  afplay api_test_1.wav")
    print("  afplay api_test_2.wav")


if __name__ == "__main__":
    main()
