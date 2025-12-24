"""测试 Modal Whisper STT WebSocket 服务"""

import asyncio
import websockets
import json
import base64
import wave
import numpy as np

# Modal WebSocket URL
WS_URL = "wss://yuanbopang--whisper-stt-wrapper.modal.run/ws/stt"

async def test_websocket_stt():
    """测试 WebSocket STT 服务"""
    print(f"连接到 Whisper STT 服务: {WS_URL}")

    try:
        async with websockets.connect(WS_URL) as websocket:
            print("✓ WebSocket 连接成功")

            # 生成测试音频数据 (1秒静音 PCM 16-bit, 16kHz)
            sample_rate = 16000
            duration = 2  # 2秒
            num_samples = sample_rate * duration

            # 生成简单的正弦波作为测试音频 (440 Hz, A音)
            t = np.linspace(0, duration, num_samples, False)
            audio_signal = np.sin(2 * np.pi * 440 * t)

            # 转换为 16-bit PCM
            audio_int16 = (audio_signal * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()

            print(f"发送测试音频数据: {len(audio_bytes)} bytes ({duration}秒, {sample_rate}Hz)")

            # 分块发送音频数据（模拟实时流）
            chunk_size = 3200  # 每块 100ms (16000 * 2 bytes * 0.1)
            for i in range(0, len(audio_bytes), chunk_size):
                chunk = audio_bytes[i:i+chunk_size]

                # Base64 编码
                audio_b64 = base64.b64encode(chunk).decode('utf-8')

                # 发送 JSON 消息
                message = json.dumps({
                    "audio_data": audio_b64
                })

                await websocket.send(message)
                print(f"  发送音频块 {i//chunk_size + 1}/{(len(audio_bytes) + chunk_size - 1)//chunk_size}")

                # 模拟实时流，稍微延迟
                await asyncio.sleep(0.05)

            print("\n等待转录结果...")

            # 等待接收转录结果 (最多等待10秒)
            try:
                result = await asyncio.wait_for(websocket.recv(), timeout=15.0)
                result_data = json.loads(result)

                print("\n✓ 收到转录结果:")
                print(f"  类型: {result_data.get('message_type')}")
                print(f"  文本: {result_data.get('text')}")
                print(f"  语言: {result_data.get('language')}")
                print(f"  置信度: {result_data.get('confidence')}")

            except asyncio.TimeoutError:
                print("⚠️  等待转录结果超时（可能音频太短或无法识别）")

            print("\n测试完成！")

    except websockets.exceptions.WebSocketException as e:
        print(f"✗ WebSocket 连接错误: {e}")
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()


async def test_with_audio_file(audio_file_path: str):
    """使用真实音频文件测试"""
    print(f"连接到 Whisper STT 服务: {WS_URL}")
    print(f"音频文件: {audio_file_path}")

    try:
        async with websockets.connect(WS_URL) as websocket:
            print("✓ WebSocket 连接成功")

            # 读取 WAV 文件
            with wave.open(audio_file_path, 'rb') as wav_file:
                sample_rate = wav_file.getframerate()
                num_channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                num_frames = wav_file.getnframes()

                print(f"音频参数: {sample_rate}Hz, {num_channels}通道, {sample_width*8}bit")

                # 检查格式
                if sample_rate != 16000:
                    print(f"⚠️  警告: 采样率应为 16000Hz，当前为 {sample_rate}Hz")
                if num_channels != 1:
                    print(f"⚠️  警告: 应为单声道，当前为 {num_channels}声道")
                if sample_width != 2:
                    print(f"⚠️  警告: 应为 16-bit，当前为 {sample_width*8}-bit")

                # 读取所有帧
                audio_bytes = wav_file.readframes(num_frames)

                print(f"发送音频数据: {len(audio_bytes)} bytes ({num_frames/sample_rate:.2f}秒)")

            # 创建发送和接收任务
            async def send_audio():
                """发送音频数据"""
                chunk_size = 3200  # 100ms
                try:
                    for i in range(0, len(audio_bytes), chunk_size):
                        chunk = audio_bytes[i:i+chunk_size]

                        # Base64 编码
                        audio_b64 = base64.b64encode(chunk).decode('utf-8')

                        # 发送 JSON 消息
                        message = json.dumps({
                            "audio_data": audio_b64
                        })

                        await websocket.send(message)
                        if i % (chunk_size * 10) == 0:  # 每10个块打印一次
                            print(f"  发送音频块 {i//chunk_size + 1}/{(len(audio_bytes) + chunk_size - 1)//chunk_size}")

                        await asyncio.sleep(0.05)
                    print("✓ 所有音频数据已发送")
                except Exception as e:
                    print(f"发送错误: {e}")

            async def receive_results():
                """接收转录结果"""
                results_count = 0
                try:
                    while True:
                        result = await asyncio.wait_for(websocket.recv(), timeout=45.0)
                        result_data = json.loads(result)
                        results_count += 1

                        print(f"\n✓ 收到转录结果 #{results_count}:")
                        print(f"  类型: {result_data.get('message_type')}")
                        print(f"  文本: {result_data.get('text')}")
                        print(f"  语言: {result_data.get('language')}")
                        print(f"  置信度: {result_data.get('confidence'):.2f}")

                except asyncio.TimeoutError:
                    if results_count == 0:
                        print("\n⚠️  未收到任何转录结果")
                    else:
                        print(f"\n✓ 共收到 {results_count} 个转录结果")
                except websockets.exceptions.ConnectionClosed:
                    print(f"\n✓ 连接关闭，共收到 {results_count} 个转录结果")
                except Exception as e:
                    print(f"\n接收错误: {e}")

            # 并行运行发送和接收任务
            await asyncio.gather(
                send_audio(),
                receive_results()
            )

            print("\n测试完成！")

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys

    print("="*60)
    print("Modal Whisper STT WebSocket 测试")
    print("="*60)

    if len(sys.argv) > 1:
        # 使用提供的音频文件
        audio_file = sys.argv[1]
        asyncio.run(test_with_audio_file(audio_file))
    else:
        # 使用合成音频测试
        print("使用合成音频测试（440Hz 正弦波）")
        print("如需使用真实音频文件，请提供 WAV 文件路径作为参数")
        print()
        asyncio.run(test_websocket_stt())
