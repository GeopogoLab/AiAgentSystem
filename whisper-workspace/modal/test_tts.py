"""测试 Modal XTTS-v2 TTS 服务"""

import requests
import base64
import wave
import time
from datetime import datetime

# Modal REST API URL
TTS_URL = "https://yuanbopang--coqui-xtts-tts-wrapper.modal.run/tts"
HEALTH_URL = "https://yuanbopang--coqui-xtts-tts-wrapper.modal.run/health"
LANGUAGES_URL = "https://yuanbopang--coqui-xtts-tts-wrapper.modal.run/languages"

# ANSI 颜色代码
class Colors:
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def test_health_check():
    """测试健康检查"""
    print(f"\n{Colors.BLUE}📡 测试健康检查...{Colors.RESET}")

    try:
        response = requests.get(HEALTH_URL, timeout=10)
        response.raise_for_status()

        data = response.json()
        print(f"{Colors.GREEN}✓ 健康检查通过{Colors.RESET}")
        print(f"  状态: {data.get('status')}")
        print(f"  服务: {data.get('service')}")
        return True

    except Exception as e:
        print(f"{Colors.RED}✗ 健康检查失败: {e}{Colors.RESET}")
        return False


def test_list_languages():
    """列出支持的语言"""
    print(f"\n{Colors.BLUE}🌍 获取支持的语言列表...{Colors.RESET}")

    try:
        response = requests.get(LANGUAGES_URL, timeout=10)
        response.raise_for_status()

        data = response.json()
        languages = data.get('languages', {})

        print(f"{Colors.GREEN}✓ 支持 {len(languages)} 种语言:{Colors.RESET}")
        for code, name in languages.items():
            print(f"  {code}: {name}")
        return True

    except Exception as e:
        print(f"{Colors.RED}✗ 获取语言列表失败: {e}{Colors.RESET}")
        return False


def test_tts_synthesis(text: str, language: str = "en", output_file: str = "output_tts.wav"):
    """
    测试 TTS 合成

    Args:
        text: 要合成的文本
        language: 语言代码
        output_file: 输出文件名
    """
    print(f"\n{Colors.CYAN}🎤 测试 TTS 合成...{Colors.RESET}")
    print(f"  文本: {text}")
    print(f"  语言: {language}")
    print(f"  输出: {output_file}")

    try:
        # 发送 TTS 请求
        start_time = time.time()

        payload = {
            "text": text,
            "language": language,
        }

        print(f"\n{Colors.YELLOW}⏳ 发送请求到 GPU 服务器...{Colors.RESET}")
        response = requests.post(TTS_URL, json=payload, timeout=120)  # TTS 可能需要较长时间
        response.raise_for_status()

        elapsed = time.time() - start_time

        # 解析响应
        data = response.json()
        audio_b64 = data.get('audio_b64')
        sample_rate = data.get('sample_rate', 24000)

        if not audio_b64:
            print(f"{Colors.RED}✗ 未收到音频数据{Colors.RESET}")
            return False

        # 解码音频
        audio_bytes = base64.b64decode(audio_b64)

        # 保存为 WAV 文件
        with open(output_file, 'wb') as f:
            f.write(audio_bytes)

        # 获取音频信息
        with wave.open(output_file, 'rb') as wav_file:
            n_channels = wav_file.getnchannels()
            sampwidth = wav_file.getsampwidth()
            framerate = wav_file.getframerate()
            n_frames = wav_file.getnframes()
            duration = n_frames / framerate

        print(f"\n{Colors.GREEN}✓ TTS 合成成功!{Colors.RESET}")
        print(f"  耗时: {elapsed:.2f}秒")
        print(f"  音频大小: {len(audio_bytes)} bytes")
        print(f"  音频时长: {duration:.2f}秒")
        print(f"  采样率: {framerate}Hz")
        print(f"  声道: {n_channels}")
        print(f"  位深: {sampwidth*8}bit")
        print(f"  已保存: {output_file}")

        return True

    except requests.exceptions.Timeout:
        print(f"{Colors.RED}✗ 请求超时 (GPU 可能正在冷启动，首次请求需要 40-60 秒){Colors.RESET}")
        return False
    except Exception as e:
        print(f"{Colors.RED}✗ TTS 合成失败: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        return False


def test_voice_cloning(text: str, reference_audio: str, language: str = "en", output_file: str = "output_cloned.wav"):
    """
    测试声音克隆

    Args:
        text: 要合成的文本
        reference_audio: 参考音频文件路径 (WAV)
        language: 语言代码
        output_file: 输出文件名
    """
    print(f"\n{Colors.CYAN}🎭 测试声音克隆...{Colors.RESET}")
    print(f"  文本: {text}")
    print(f"  参考音频: {reference_audio}")
    print(f"  语言: {language}")
    print(f"  输出: {output_file}")

    try:
        # 读取参考音频
        with open(reference_audio, 'rb') as f:
            reference_audio_bytes = f.read()

        reference_audio_b64 = base64.b64encode(reference_audio_bytes).decode('utf-8')

        print(f"  参考音频大小: {len(reference_audio_bytes)} bytes")

        # 发送 TTS 请求
        start_time = time.time()

        payload = {
            "text": text,
            "language": language,
            "speaker_wav_b64": reference_audio_b64,
        }

        print(f"\n{Colors.YELLOW}⏳ 发送声音克隆请求...{Colors.RESET}")
        response = requests.post(TTS_URL, json=payload, timeout=180)
        response.raise_for_status()

        elapsed = time.time() - start_time

        # 解析响应
        data = response.json()
        audio_b64 = data.get('audio_b64')

        if not audio_b64:
            print(f"{Colors.RED}✗ 未收到音频数据{Colors.RESET}")
            return False

        # 解码音频
        audio_bytes = base64.b64decode(audio_b64)

        # 保存为 WAV 文件
        with open(output_file, 'wb') as f:
            f.write(audio_bytes)

        # 获取音频信息
        with wave.open(output_file, 'rb') as wav_file:
            duration = wav_file.getnframes() / wav_file.getframerate()

        print(f"\n{Colors.GREEN}✓ 声音克隆成功!{Colors.RESET}")
        print(f"  耗时: {elapsed:.2f}秒")
        print(f"  音频大小: {len(audio_bytes)} bytes")
        print(f"  音频时长: {duration:.2f}秒")
        print(f"  已保存: {output_file}")

        return True

    except Exception as e:
        print(f"{Colors.RED}✗ 声音克隆失败: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        return False


def run_comprehensive_tests():
    """运行综合测试"""
    print("\n" + "=" * 70)
    print(f"{Colors.BOLD}{Colors.CYAN}🎙️  Modal XTTS-v2 TTS 综合测试{Colors.RESET}")
    print("=" * 70)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    results = []

    # 测试 1: 健康检查
    results.append(("健康检查", test_health_check()))

    # 测试 2: 语言列表
    results.append(("语言列表", test_list_languages()))

    # 测试 3: 英文 TTS
    results.append((
        "英文 TTS",
        test_tts_synthesis(
            text="Hello! This is a test of the XTTS voice synthesis system. It can generate natural-sounding speech in multiple languages.",
            language="en",
            output_file="test_output_en.wav"
        )
    ))

    # 测试 4: 中文 TTS
    results.append((
        "中文 TTS",
        test_tts_synthesis(
            text="你好！这是一个语音合成系统的测试。它可以生成多种语言的自然语音。",
            language="zh-cn",
            output_file="test_output_zh.wav"
        )
    ))

    # 测试 5: 长文本 TTS
    results.append((
        "长文本 TTS",
        test_tts_synthesis(
            text="The quick brown fox jumps over the lazy dog. This is a pangram sentence that contains every letter of the English alphabet. It is commonly used for testing fonts, keyboards, and voice synthesis systems. The quality of text-to-speech systems has improved dramatically in recent years thanks to advances in deep learning.",
            language="en",
            output_file="test_output_long.wav"
        )
    ))

    # 打印测试摘要
    print("\n" + "=" * 70)
    print(f"{Colors.BOLD}{Colors.CYAN}📊 测试摘要{Colors.RESET}")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = f"{Colors.GREEN}✓ 通过{Colors.RESET}" if result else f"{Colors.RED}✗ 失败{Colors.RESET}"
        print(f"{test_name}: {status}")

    print("=" * 70)
    print(f"总计: {passed}/{total} 通过")
    print("=" * 70)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # 命令行模式
        mode = sys.argv[1]

        if mode == "health":
            test_health_check()

        elif mode == "languages":
            test_list_languages()

        elif mode == "tts":
            # python test_tts.py tts "Your text here" [language] [output_file]
            text = sys.argv[2] if len(sys.argv) > 2 else "Hello, this is a test."
            language = sys.argv[3] if len(sys.argv) > 3 else "en"
            output = sys.argv[4] if len(sys.argv) > 4 else "output_tts.wav"

            test_tts_synthesis(text, language, output)

        elif mode == "clone":
            # python test_tts.py clone "Your text here" reference.wav [language] [output_file]
            if len(sys.argv) < 4:
                print("用法: python test_tts.py clone <text> <reference_audio.wav> [language] [output_file]")
                sys.exit(1)

            text = sys.argv[2]
            reference = sys.argv[3]
            language = sys.argv[4] if len(sys.argv) > 4 else "en"
            output = sys.argv[5] if len(sys.argv) > 5 else "output_cloned.wav"

            test_voice_cloning(text, reference, language, output)

        else:
            print(f"未知模式: {mode}")
            print("用法:")
            print("  python test_tts.py health")
            print("  python test_tts.py languages")
            print("  python test_tts.py tts [text] [language] [output_file]")
            print("  python test_tts.py clone <text> <reference.wav> [language] [output_file]")

    else:
        # 默认：运行综合测试
        run_comprehensive_tests()
