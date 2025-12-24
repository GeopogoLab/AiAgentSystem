"""WebSocket 实时语音识别测试
模拟真实的流式音频输入场景
"""

import asyncio
import websockets
import json
import base64
import wave
import time
from datetime import datetime
from typing import Optional

# Modal WebSocket URL
WS_URL = "wss://yuanbopang--whisper-stt-wrapper.modal.run/ws/stt"

# ANSI 颜色代码
class Colors:
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


class WebSocketSTTClient:
    """WebSocket 语音识别客户端"""

    def __init__(self, url: str = WS_URL):
        self.url = url
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.results_received = []
        self.start_time = None
        self.first_result_time = None

    async def connect(self):
        """建立 WebSocket 连接"""
        print(f"{Colors.BLUE}🔌 连接到: {self.url}{Colors.RESET}")
        connect_start = time.time()

        self.websocket = await websockets.connect(self.url)
        self.start_time = time.time()

        connect_time = time.time() - connect_start
        print(f"{Colors.GREEN}✓ 连接成功 (耗时: {connect_time:.2f}秒){Colors.RESET}\n")

    async def disconnect(self):
        """关闭连接"""
        if self.websocket:
            await self.websocket.close()
            print(f"\n{Colors.YELLOW}🔌 连接已关闭{Colors.RESET}")

    async def stream_audio_file(self, audio_file: str, chunk_duration_ms: int = 100):
        """
        流式发送音频文件（模拟实时麦克风输入）

        Args:
            audio_file: WAV 文件路径
            chunk_duration_ms: 每个音频块的毫秒数（模拟实时采集）
        """
        print(f"{Colors.CYAN}🎤 开始流式发送音频...{Colors.RESET}")
        print(f"   文件: {audio_file}")
        print(f"   块大小: {chunk_duration_ms}ms\n")

        # 读取音频文件
        with wave.open(audio_file, 'rb') as wav_file:
            sample_rate = wav_file.getframerate()
            num_channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()

            # 检查格式
            assert sample_rate == 16000, f"采样率必须是 16000Hz，当前为 {sample_rate}Hz"
            assert num_channels == 1, f"必须是单声道，当前为 {num_channels}声道"
            assert sample_width == 2, f"必须是 16-bit，当前为 {sample_width*8}-bit"

            # 计算每个块的字节数
            bytes_per_chunk = int(sample_rate * (chunk_duration_ms / 1000) * 2)  # 16-bit = 2 bytes

            total_frames = wav_file.getnframes()
            total_duration = total_frames / sample_rate

            print(f"   音频时长: {total_duration:.2f}秒")
            print(f"   每块字节: {bytes_per_chunk} bytes\n")

            # 流式发送音频
            chunk_count = 0
            bytes_sent = 0

            while True:
                # 读取一个音频块
                audio_chunk = wav_file.readframes(int(bytes_per_chunk / 2))
                if not audio_chunk:
                    break

                chunk_count += 1
                bytes_sent += len(audio_chunk)

                # Base64 编码
                audio_b64 = base64.b64encode(audio_chunk).decode('utf-8')

                # 发送 JSON 消息
                message = json.dumps({"audio_data": audio_b64})
                await self.websocket.send(message)

                # 显示进度
                progress = (bytes_sent / (total_frames * 2)) * 100
                if chunk_count % 10 == 0:
                    print(f"\r   {Colors.CYAN}发送进度: {progress:.1f}% ({chunk_count} 块){Colors.RESET}", end='', flush=True)

                # 模拟实时采集延迟
                await asyncio.sleep(chunk_duration_ms / 1000)

            print(f"\n{Colors.GREEN}✓ 音频发送完成 (共 {chunk_count} 块, {bytes_sent} bytes){Colors.RESET}\n")

    async def receive_results(self, timeout: float = 60.0):
        """
        接收转录结果

        Args:
            timeout: 超时时间（秒）
        """
        print(f"{Colors.YELLOW}👂 等待转录结果...{Colors.RESET}\n")

        try:
            while True:
                result = await asyncio.wait_for(self.websocket.recv(), timeout=timeout)
                result_data = json.loads(result)

                # 记录首个结果时间
                if self.first_result_time is None:
                    self.first_result_time = time.time() - self.start_time

                elapsed = time.time() - self.start_time
                result_num = len(self.results_received) + 1

                # 保存结果
                self.results_received.append({
                    'time': elapsed,
                    'text': result_data.get('text', ''),
                    'language': result_data.get('language', 'unknown'),
                    'confidence': result_data.get('confidence', 0.0)
                })

                # 显示结果
                text = result_data.get('text', '')
                language = result_data.get('language', 'unknown')
                confidence = result_data.get('confidence', 0.0)

                print(f"{Colors.GREEN}{Colors.BOLD}📝 结果 #{result_num}{Colors.RESET} {Colors.YELLOW}({elapsed:.2f}秒){Colors.RESET}")
                print(f"   {Colors.CYAN}文本:{Colors.RESET} {text}")
                print(f"   {Colors.CYAN}语言:{Colors.RESET} {language}")
                print(f"   {Colors.CYAN}置信度:{Colors.RESET} {confidence:.2f}\n")

        except asyncio.TimeoutError:
            total_elapsed = time.time() - self.start_time

            if len(self.results_received) == 0:
                print(f"{Colors.RED}⚠️  超时 ({timeout}秒) - 未收到任何结果{Colors.RESET}")
            else:
                print(f"{Colors.GREEN}✓ 接收完成 (超时退出，共收到 {len(self.results_received)} 个结果){Colors.RESET}")

        except websockets.exceptions.ConnectionClosed:
            print(f"{Colors.YELLOW}🔌 连接已关闭{Colors.RESET}")

    def print_summary(self):
        """打印测试摘要"""
        print("\n" + "=" * 70)
        print(f"{Colors.BOLD}{Colors.CYAN}📊 测试摘要{Colors.RESET}")
        print("=" * 70)

        if not self.results_received:
            print(f"{Colors.RED}未收到任何转录结果{Colors.RESET}")
            print("=" * 70)
            return

        total_time = time.time() - self.start_time

        print(f"{Colors.CYAN}总耗时:{Colors.RESET} {total_time:.2f}秒")
        print(f"{Colors.CYAN}首个结果时间:{Colors.RESET} {self.first_result_time:.2f}秒 (包含 GPU 冷启动)")
        print(f"{Colors.CYAN}转录结果数:{Colors.RESET} {len(self.results_received)}")
        print(f"{Colors.CYAN}平均每结果:{Colors.RESET} {total_time / len(self.results_received):.2f}秒")

        print(f"\n{Colors.BOLD}转录内容:{Colors.RESET}")
        print("-" * 70)
        for i, result in enumerate(self.results_received, 1):
            print(f"{i}. {result['text']}")

        print("=" * 70)


async def test_streaming_stt():
    """运行流式语音识别测试"""

    print("\n" + "=" * 70)
    print(f"{Colors.BOLD}{Colors.CYAN}🎙️  WebSocket 实时语音识别测试{Colors.RESET}")
    print("=" * 70)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70 + "\n")

    client = WebSocketSTTClient()

    try:
        # 1. 建立连接
        await client.connect()

        # 2. 并行执行：流式发送音频 + 接收结果
        await asyncio.gather(
            client.stream_audio_file('test_audio_16k.wav', chunk_duration_ms=100),
            client.receive_results(timeout=60.0)
        )

        # 3. 打印摘要
        client.print_summary()

    except Exception as e:
        print(f"\n{Colors.RED}❌ 错误: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()

    finally:
        # 4. 关闭连接
        await client.disconnect()


async def test_rapid_streaming():
    """快速流式测试（模拟高速网络）"""

    print("\n" + "=" * 70)
    print(f"{Colors.BOLD}{Colors.CYAN}⚡ 快速流式测试 (20ms 块){Colors.RESET}")
    print("=" * 70 + "\n")

    client = WebSocketSTTClient()

    try:
        await client.connect()

        await asyncio.gather(
            client.stream_audio_file('test_audio_16k.wav', chunk_duration_ms=20),
            client.receive_results(timeout=60.0)
        )

        client.print_summary()

    finally:
        await client.disconnect()


async def test_slow_streaming():
    """慢速流式测试（模拟慢速网络）"""

    print("\n" + "=" * 70)
    print(f"{Colors.BOLD}{Colors.CYAN}🐌 慢速流式测试 (500ms 块){Colors.RESET}")
    print("=" * 70 + "\n")

    client = WebSocketSTTClient()

    try:
        await client.connect()

        await asyncio.gather(
            client.stream_audio_file('test_audio_16k.wav', chunk_duration_ms=500),
            client.receive_results(timeout=60.0)
        )

        client.print_summary()

    finally:
        await client.disconnect()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == "rapid":
            asyncio.run(test_rapid_streaming())
        elif mode == "slow":
            asyncio.run(test_slow_streaming())
        else:
            print(f"未知模式: {mode}")
            print("用法: python test_websocket_streaming.py [rapid|slow]")
    else:
        # 默认：标准流式测试
        asyncio.run(test_streaming_stt())
