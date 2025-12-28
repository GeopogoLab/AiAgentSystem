"""Streaming TTS Engine using Piper

本地流式文本转语音服务，使用 Piper TTS + FFmpeg 实现边生成边输出。
"""

import asyncio
import base64
import logging
import re
import subprocess
from pathlib import Path
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)


class PiperTTS:
    """Piper TTS 流式引擎

    特点：
    - 真正的流式输出（句子级）
    - CPU 友好（无需 GPU）
    - 低延迟（首字节 < 500ms）
    """

    def __init__(self, model_path: str, config_path: str, sample_rate: int = 22050):
        """初始化 Piper TTS 引擎

        Args:
            model_path: ONNX 模型文件路径
            config_path: JSON 配置文件路径
            sample_rate: 输出采样率（Hz）
        """
        self.model_path = Path(model_path)
        self.config_path = Path(config_path)
        self.sample_rate = sample_rate
        self.validate_model()
        logger.info(f"Initialized Piper TTS: {self.model_path.name}")

    def validate_model(self):
        """验证模型文件存在"""
        if not self.model_path.exists():
            raise FileNotFoundError(f"Piper model not found: {self.model_path}")
        if not self.config_path.exists():
            raise FileNotFoundError(f"Piper config not found: {self.config_path}")
        logger.info(f"Model validation passed: {self.model_path.name}")

    async def synthesize_stream(
        self,
        text: str,
        output_format: str = "mp3",
    ) -> AsyncGenerator[bytes, None]:
        """流式生成音频块

        工作流程：
        1. 将文本分句（避免单次生成过长）
        2. 逐句调用 Piper 生成 PCM 音频
        3. 通过 FFmpeg 实时转码为 MP3
        4. yield 音频块（4KB chunks）

        Args:
            text: 输入文本
            output_format: 输出格式（mp3 或 wav）

        Yields:
            bytes: 音频块
        """
        # 文本预处理：分句
        sentences = self._split_sentences(text)
        logger.info(f"Split text into {len(sentences)} sentences")

        for i, sentence in enumerate(sentences):
            logger.debug(f"Synthesizing sentence {i+1}/{len(sentences)}: {sentence[:50]}...")
            async for chunk in self._synthesize_sentence(sentence, output_format):
                yield chunk

    def _split_sentences(self, text: str, max_length: int = 150) -> list[str]:
        """将文本分句

        按以下规则分句：
        1. 按句号、问号、感叹号分句
        2. 如果单句过长（> max_length），按逗号再分
        3. 保留标点符号

        Args:
            text: 输入文本
            max_length: 单句最大字符数

        Returns:
            句子列表
        """
        if not text.strip():
            return []

        # 按主要标点分句
        sentences = re.split(r'([.!?。！？]+)', text)

        # 重新组合（标点附加到前一句）
        result = []
        for i in range(0, len(sentences), 2):
            sentence = sentences[i]
            if i + 1 < len(sentences):
                sentence += sentences[i + 1]

            sentence = sentence.strip()
            if not sentence:
                continue

            # 如果句子过长，按逗号再分
            if len(sentence) > max_length:
                parts = re.split(r'([,，、;；:])', sentence)
                temp = ""
                for j in range(0, len(parts), 2):
                    part = parts[j]
                    if j + 1 < len(parts):
                        part += parts[j + 1]

                    if len(temp) + len(part) > max_length and temp:
                        result.append(temp.strip())
                        temp = part
                    else:
                        temp += part

                if temp:
                    result.append(temp.strip())
            else:
                result.append(sentence)

        return result

    async def _synthesize_sentence(
        self,
        sentence: str,
        output_format: str,
    ) -> AsyncGenerator[bytes, None]:
        """合成单个句子

        使用 Piper 生成 PCM 音频，通过 FFmpeg 转码为 MP3。

        Args:
            sentence: 要合成的句子
            output_format: 输出格式（mp3 或 wav）

        Yields:
            bytes: 音频块
        """
        try:
            # Piper 命令（输出 WAV 到 stdout）
            piper_cmd = [
                "piper",
                "--model", str(self.model_path),
                "--config", str(self.config_path),
                "--output-raw",  # 输出原始 PCM 到 stdout
            ]

            # FFmpeg 命令（PCM → MP3）
            if output_format == "mp3":
                ffmpeg_cmd = [
                    "ffmpeg",
                    "-f", "s16le",                  # 输入格式：PCM 16-bit LE
                    "-ar", "22050",                 # Piper 默认采样率
                    "-ac", "1",                     # 单声道
                    "-i", "pipe:0",                 # 从 stdin 读取
                    "-f", "mp3",                    # 输出 MP3
                    "-ab", "64k",                   # 比特率 64kbps
                    "-ar", str(self.sample_rate),   # 重采样
                    "-loglevel", "error",           # 仅显示错误
                    "pipe:1"                        # 输出到 stdout
                ]
            else:
                # WAV 输出
                ffmpeg_cmd = [
                    "ffmpeg",
                    "-f", "s16le",
                    "-ar", "22050",
                    "-ac", "1",
                    "-i", "pipe:0",
                    "-f", "wav",
                    "-loglevel", "error",
                    "pipe:1"
                ]

            # 启动 Piper 进程
            piper_proc = await asyncio.create_subprocess_exec(
                *piper_cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # 启动 FFmpeg 进程（链式处理）
            ffmpeg_proc = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # 创建三个并发任务：
            # 1. 写入文本到 Piper
            # 2. 从 Piper 读取并写入 FFmpeg
            # 3. 从 FFmpeg 读取并 yield 输出

            async def write_to_piper():
                """写入文本到 Piper"""
                if piper_proc.stdin:
                    piper_proc.stdin.write(sentence.encode("utf-8"))
                    piper_proc.stdin.write(b"\n")
                    await piper_proc.stdin.drain()
                    piper_proc.stdin.close()

            async def pipe_piper_to_ffmpeg():
                """从 Piper 读取并写入 FFmpeg"""
                if piper_proc.stdout and ffmpeg_proc.stdin:
                    try:
                        while True:
                            chunk = await piper_proc.stdout.read(4096)
                            if not chunk:
                                break
                            ffmpeg_proc.stdin.write(chunk)
                            await ffmpeg_proc.stdin.drain()
                    finally:
                        ffmpeg_proc.stdin.close()

            async def read_from_ffmpeg():
                """从 FFmpeg 读取完整输出"""
                if ffmpeg_proc.stdout:
                    return await ffmpeg_proc.stdout.read()
                return b""
            # 启动所有任务
            write_task = asyncio.create_task(write_to_piper())
            pipe_task = asyncio.create_task(pipe_piper_to_ffmpeg())
            read_task = asyncio.create_task(read_from_ffmpeg())

            # 等待所有任务完成
            await write_task
            await pipe_task
            audio_bytes = await read_task

            # 等待进程结束
            await piper_proc.wait()
            await ffmpeg_proc.wait()

            # 检查错误
            if piper_proc.returncode != 0:
                stderr = await piper_proc.stderr.read() if piper_proc.stderr else b""
                logger.error(f"Piper error: {stderr.decode('utf-8', errors='ignore')}")
                raise RuntimeError(f"Piper synthesis failed: {stderr[:200]}")

            if ffmpeg_proc.returncode != 0:
                stderr = await ffmpeg_proc.stderr.read() if ffmpeg_proc.stderr else b""
                logger.error(f"FFmpeg error: {stderr.decode('utf-8', errors='ignore')}")
                raise RuntimeError(f"FFmpeg encoding failed: {stderr[:200]}")

            # Yield 所有音频块
            if audio_bytes:
                yield audio_bytes

        except FileNotFoundError as e:
            logger.error(f"Command not found: {e}")
            raise RuntimeError(
                f"Missing dependency: {e}. Please install Piper and FFmpeg."
            )
        except Exception as e:
            logger.error(f"TTS synthesis error: {e}")
            raise


# 全局 TTS 实例（单例模式）
_tts_engine: Optional[PiperTTS] = None


def get_tts_engine(config) -> PiperTTS:
    """获取或创建 TTS 引擎（单例模式）

    Args:
        config: 应用配置对象

    Returns:
        PiperTTS 实例
    """
    global _tts_engine
    if _tts_engine is None:
        model_path = config.PIPER_MODEL_PATH
        config_path = config.PIPER_CONFIG_PATH
        sample_rate = config.PIPER_SAMPLE_RATE
        _tts_engine = PiperTTS(model_path, config_path, sample_rate)
        logger.info("Created global PiperTTS instance")
    return _tts_engine


def check_dependencies() -> tuple[bool, list[str]]:
    """检查 Piper 和 FFmpeg 是否安装

    Returns:
        (是否全部安装, 缺失的依赖列表)
    """
    missing = []

    # 检查 Piper
    try:
        subprocess.run(
            ["piper", "--version"],
            capture_output=True,
            check=True,
            timeout=5
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        missing.append("piper")

    # 检查 FFmpeg
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=True,
            timeout=5
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        missing.append("ffmpeg")

    return (len(missing) == 0, missing)
