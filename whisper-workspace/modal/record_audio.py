#!/usr/bin/env python3
"""录音工具 - 录制音频并保存为 WAV 格式用于测试语音转文字"""

import pyaudio
import wave
import sys
import os
from datetime import datetime

# 音频参数配置（符合 Whisper STT 要求）
CHUNK = 1024  # 每次读取的音频块大小
FORMAT = pyaudio.paInt16  # 16-bit
CHANNELS = 1  # 单声道
RATE = 16000  # 16kHz 采样率

def list_audio_devices():
    """列出所有可用的音频设备"""
    p = pyaudio.PyAudio()
    print("\n可用的音频输入设备:")
    print("-" * 60)

    for i in range(p.get_device_count()):
        device_info = p.get_device_info_by_index(i)
        if device_info['maxInputChannels'] > 0:
            print(f"设备 {i}: {device_info['name']}")
            print(f"  最大输入通道: {device_info['maxInputChannels']}")
            print(f"  默认采样率: {int(device_info['defaultSampleRate'])} Hz")
            print()

    p.terminate()

def record_audio(duration=5, output_file=None, device_index=None):
    """
    录制音频并保存为 WAV 文件

    参数:
        duration: 录音时长（秒）
        output_file: 输出文件路径，如果为 None 则自动生成
        device_index: 音频设备索引，如果为 None 则使用默认设备

    返回:
        str: 输出文件路径
    """
    # 如果未指定输出文件，自动生成文件名
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"recording_{timestamp}.wav"

    # 确保输出文件有 .wav 扩展名
    if not output_file.endswith('.wav'):
        output_file += '.wav'

    p = pyaudio.PyAudio()

    try:
        # 打开音频流
        print(f"\n开始录音...")
        print(f"录音时长: {duration} 秒")
        print(f"采样率: {RATE} Hz")
        print(f"通道数: {CHANNELS} (单声道)")
        print(f"位深度: 16-bit")
        if device_index is not None:
            device_info = p.get_device_info_by_index(device_index)
            print(f"使用设备: {device_info['name']}")
        print(f"\n请说话...")

        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=CHUNK
        )

        frames = []

        # 录音
        for i in range(0, int(RATE / CHUNK * duration)):
            data = stream.read(CHUNK)
            frames.append(data)

            # 显示进度
            progress = (i + 1) / (RATE / CHUNK * duration)
            bar_length = 30
            filled = int(bar_length * progress)
            bar = '=' * filled + '-' * (bar_length - filled)
            print(f'\r[{bar}] {int(progress * 100)}%', end='', flush=True)

        print("\n\n录音完成!")

        # 停止并关闭流
        stream.stop_stream()
        stream.close()

        # 保存为 WAV 文件
        print(f"正在保存到: {output_file}")
        with wave.open(output_file, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))

        # 获取文件信息
        file_size = os.path.getsize(output_file)
        print(f"✓ 文件已保存: {output_file}")
        print(f"  文件大小: {file_size / 1024:.2f} KB")
        print(f"  时长: {duration} 秒")

        return output_file

    except Exception as e:
        print(f"\n✗ 录音失败: {e}")
        raise
    finally:
        p.terminate()

def main():
    """主函数"""
    print("="*60)
    print("音频录制工具")
    print("="*60)

    # 解析命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] in ['-h', '--help']:
            print("\n用法:")
            print(f"  {sys.argv[0]} [时长] [输出文件] [设备索引]")
            print("\n参数:")
            print("  时长        录音时长（秒），默认 5 秒")
            print("  输出文件     输出 WAV 文件路径，默认自动生成")
            print("  设备索引     音频设备索引，默认使用系统默认设备")
            print("\n选项:")
            print("  -l, --list  列出所有可用的音频设备")
            print("  -h, --help  显示此帮助信息")
            print("\n示例:")
            print(f"  {sys.argv[0]}                    # 录制 5 秒")
            print(f"  {sys.argv[0]} 10                 # 录制 10 秒")
            print(f"  {sys.argv[0]} 10 test.wav        # 录制 10 秒，保存为 test.wav")
            print(f"  {sys.argv[0]} 10 test.wav 1      # 使用设备 1 录制 10 秒")
            print(f"  {sys.argv[0]} --list             # 列出所有音频设备")
            return

        if sys.argv[1] in ['-l', '--list']:
            list_audio_devices()
            return

    # 获取参数
    duration = 5  # 默认 5 秒
    output_file = None
    device_index = None

    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except ValueError:
            print(f"✗ 错误: 时长必须是整数，获得: {sys.argv[1]}")
            return

    if len(sys.argv) > 2:
        output_file = sys.argv[2]

    if len(sys.argv) > 3:
        try:
            device_index = int(sys.argv[3])
        except ValueError:
            print(f"✗ 错误: 设备索引必须是整数，获得: {sys.argv[3]}")
            return

    # 录音
    try:
        output_path = record_audio(duration, output_file, device_index)

        # 提示如何使用
        print("\n" + "="*60)
        print("可以使用以下命令测试 STT:")
        print(f"  python test_whisper_stt.py {output_path}")
        print("="*60)

    except KeyboardInterrupt:
        print("\n\n用户中断录音")
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
