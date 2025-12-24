"""WebSocket 语音识别交互式演示
实时显示转录结果的命令行工具
"""

import asyncio
import websockets
import json
import base64
import wave
import sys
from datetime import datetime

WS_URL = "wss://yuanbopang--whisper-stt-wrapper.modal.run/ws/stt"


class LiveTranscription:
    """实时转录显示器"""

    def __init__(self):
        self.results = []
        self.start_time = None

    def clear_screen(self):
        """清屏"""
        print("\033[2J\033[H", end='')

    def draw_ui(self, status="连接中...", progress=0, current_text=""):
        """绘制用户界面"""
        self.clear_screen()

        # 标题栏
        print("=" * 80)
        print(" " * 25 + "🎙️  实时语音识别演示")
        print("=" * 80)
        print()

        # 状态信息
        print(f"📡 状态: {status}")
        print(f"⏱️  时间: {datetime.now().strftime('%H:%M:%S')}")
        print()

        # 进度条
        if progress > 0:
            bar_length = 50
            filled = int(bar_length * progress / 100)
            bar = "█" * filled + "░" * (bar_length - filled)
            print(f"进度: [{bar}] {progress:.1f}%")
            print()

        # 当前识别中的文本
        if current_text:
            print("🔄 识别中:")
            print("-" * 80)
            print(f"  {current_text}")
            print("-" * 80)
            print()

        # 历史结果
        if self.results:
            print(f"📝 已识别结果 ({len(self.results)}):")
            print("-" * 80)
            for i, result in enumerate(self.results[-5:], 1):  # 只显示最后5个
                print(f"{i}. {result}")
            if len(self.results) > 5:
                print(f"   ... (还有 {len(self.results) - 5} 条)")
            print("-" * 80)

        print()
        print("💡 提示: 按 Ctrl+C 停止")

    async def run_demo(self, audio_file: str):
        """运行演示"""
        self.draw_ui("正在连接服务器...")

        try:
            # 连接 WebSocket
            async with websockets.connect(WS_URL) as ws:
                self.start_time = asyncio.get_event_loop().time()
                self.draw_ui("✅ 已连接，开始发送音频...")

                # 读取音频
                with wave.open(audio_file, 'rb') as wav_file:
                    sample_rate = wav_file.getframerate()
                    total_frames = wav_file.getnframes()
                    total_duration = total_frames / sample_rate

                    # 流式发送和接收
                    async def send_audio():
                        chunk_size = 3200  # 100ms
                        sent_bytes = 0
                        total_bytes = total_frames * 2

                        while True:
                            chunk = wav_file.readframes(int(chunk_size / 2))
                            if not chunk:
                                break

                            audio_b64 = base64.b64encode(chunk).decode()
                            await ws.send(json.dumps({"audio_data": audio_b64}))

                            sent_bytes += len(chunk)
                            progress = (sent_bytes / total_bytes) * 100

                            # 更新UI
                            elapsed = asyncio.get_event_loop().time() - self.start_time
                            status = f"🎤 发送中 ({elapsed:.1f}秒)"
                            self.draw_ui(status, progress)

                            await asyncio.sleep(0.1)  # 100ms 延迟

                        self.draw_ui("✅ 音频发送完成，等待结果...", 100)

                    async def receive_results():
                        try:
                            while True:
                                result = await asyncio.wait_for(ws.recv(), timeout=30.0)
                                result_data = json.loads(result)

                                text = result_data.get('text', '')
                                self.results.append(text)

                                # 更新UI显示新结果
                                elapsed = asyncio.get_event_loop().time() - self.start_time
                                status = f"✅ 收到结果 #{len(self.results)} ({elapsed:.1f}秒)"
                                self.draw_ui(status, 100, text)

                                await asyncio.sleep(0.5)  # 短暂显示

                        except asyncio.TimeoutError:
                            self.draw_ui("✅ 识别完成", 100)

                    # 并行执行
                    await asyncio.gather(send_audio(), receive_results())

        except KeyboardInterrupt:
            self.draw_ui("⚠️  用户中断", 0)

        except Exception as e:
            self.draw_ui(f"❌ 错误: {str(e)}", 0)

        # 显示最终结果
        print("\n\n" + "=" * 80)
        print("📊 识别完成!")
        print("=" * 80)
        print(f"总结果数: {len(self.results)}")
        print()
        print("完整转录:")
        print("-" * 80)
        for i, text in enumerate(self.results, 1):
            print(f"{i}. {text}")
        print("=" * 80)


async def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python demo_websocket_stt.py <audio_file.wav>")
        print("示例: python demo_websocket_stt.py test_audio_16k.wav")
        sys.exit(1)

    audio_file = sys.argv[1]

    demo = LiveTranscription()
    await demo.run_demo(audio_file)


if __name__ == "__main__":
    asyncio.run(main())
