"""AssemblyAI 语音转文本服务"""
import asyncio
import httpx
from .config import config


class AssemblyAISTT:
    """AssemblyAI 语音转文本客户端"""

    def __init__(self):
        """初始化 STT 客户端"""
        self.api_key = config.ASSEMBLYAI_API_KEY
        self.base_url = config.ASSEMBLYAI_API_URL
        self.headers = {
            "authorization": self.api_key,
            "content-type": "application/json"
        }

    async def upload_file(self, file_path: str) -> str:
        """
        上传音频文件到 AssemblyAI

        Args:
            file_path: 音频文件路径

        Returns:
            上传后的文件 URL
        """
        upload_url = f"{self.base_url}/upload"

        async with httpx.AsyncClient() as client:
            with open(file_path, "rb") as f:
                response = await client.post(
                    upload_url,
                    headers={"authorization": self.api_key},
                    files={"file": f}
                )

            if response.status_code != 200:
                raise Exception(f"上传文件失败: {response.text}")

            return response.json()["upload_url"]

    async def transcribe(self, audio_url: str, language_code: str = "en") -> dict:
        """
        转录音频（异步等待结果）

        Args:
            audio_url: 音频文件 URL
            language_code: 语言代码（zh 表示中文）

        Returns:
            转录结果
        """
        # 创建转录任务
        transcript_url = f"{self.base_url}/transcript"

        async with httpx.AsyncClient(timeout=60.0) as client:
            # 提交转录请求
            response = await client.post(
                transcript_url,
                headers=self.headers,
                json={
                    "audio_url": audio_url,
                    "language_code": language_code
                }
            )

            if response.status_code != 200:
                raise Exception(f"创建转录任务失败: {response.text}")

            transcript_id = response.json()["id"]

            # 轮询转录状态
            polling_url = f"{transcript_url}/{transcript_id}"
            max_attempts = 60  # 最多等待 60 次
            attempt = 0

            while attempt < max_attempts:
                response = await client.get(polling_url, headers=self.headers)

                if response.status_code != 200:
                    raise Exception(f"查询转录状态失败: {response.text}")

                result = response.json()
                status = result["status"]

                if status == "completed":
                    return result
                elif status == "error":
                    raise Exception(f"转录失败: {result.get('error', 'Unknown error')}")

                # 等待 1 秒后重试
                await asyncio.sleep(1)
                attempt += 1

            raise Exception("转录超时")

    async def transcribe_file(self, file_path: str, language_code: str = "en") -> str:
        """
        从本地文件转录音频（完整流程）

        Args:
            file_path: 本地音频文件路径
            language_code: 语言代码

        Returns:
            转录文本
        """
        # 1. 上传文件
        audio_url = await self.upload_file(file_path)

        # 2. 转录
        result = await self.transcribe(audio_url, language_code)

        # 3. 返回文本
        return result.get("text", "")


# 全局 STT 实例
stt_client = AssemblyAISTT()
