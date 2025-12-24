"""将音频文件重采样到 16kHz"""

import wave
import numpy as np
from scipy import signal

def resample_wav(input_file, output_file, target_rate=16000):
    """将 WAV 文件重采样到目标采样率"""

    # 读取原始音频
    with wave.open(input_file, 'rb') as wav_in:
        # 获取参数
        n_channels = wav_in.getnchannels()
        sampwidth = wav_in.getsampwidth()
        framerate = wav_in.getframerate()
        n_frames = wav_in.getnframes()

        print(f"原始音频参数:")
        print(f"  采样率: {framerate} Hz")
        print(f"  声道数: {n_channels}")
        print(f"  位深: {sampwidth * 8} bit")
        print(f"  总帧数: {n_frames}")
        print(f"  时长: {n_frames / framerate:.2f} 秒")

        # 读取音频数据
        audio_data = wav_in.readframes(n_frames)

        # 转换为 numpy 数组
        if sampwidth == 1:
            dtype = np.uint8
        elif sampwidth == 2:
            dtype = np.int16
        else:
            dtype = np.int32

        audio_array = np.frombuffer(audio_data, dtype=dtype)

        # 如果是立体声，转换为单声道
        if n_channels == 2:
            audio_array = audio_array.reshape(-1, 2).mean(axis=1).astype(dtype)
            n_channels = 1
            print(f"\n转换立体声为单声道")

        # 重采样
        if framerate != target_rate:
            print(f"\n重采样: {framerate} Hz -> {target_rate} Hz")
            num_samples = int(len(audio_array) * target_rate / framerate)
            audio_resampled = signal.resample(audio_array, num_samples)
            audio_resampled = audio_resampled.astype(dtype)
        else:
            audio_resampled = audio_array

        # 写入新文件
        with wave.open(output_file, 'wb') as wav_out:
            wav_out.setnchannels(n_channels)
            wav_out.setsampwidth(sampwidth)
            wav_out.setframerate(target_rate)
            wav_out.writeframes(audio_resampled.tobytes())

        print(f"\n✓ 重采样完成")
        print(f"  输出文件: {output_file}")
        print(f"  采样率: {target_rate} Hz")
        print(f"  声道数: {n_channels}")
        print(f"  位深: {sampwidth * 8} bit")
        print(f"  总帧数: {len(audio_resampled)}")
        print(f"  时长: {len(audio_resampled) / target_rate:.2f} 秒")

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python resample_audio.py <input.wav> [output.wav] [target_rate]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "resampled_16k.wav"
    target_rate = int(sys.argv[3]) if len(sys.argv) > 3 else 16000

    resample_wav(input_file, output_file, target_rate)
