"""配置文件"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class Config:
    """应用配置"""

    # API Keys
    ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY", "")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", os.getenv("OPENAI_API_KEY", ""))

    # Database
    DATABASE_PATH = os.getenv("DATABASE_PATH", "./tea_orders.db")

    # Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))

    # AssemblyAI
    ASSEMBLYAI_API_URL = "https://api.assemblyai.com/v2"
    ASSEMBLYAI_TTS_VOICE = os.getenv("ASSEMBLYAI_TTS_VOICE", "alloy")

    # LLM Provider (OpenRouter 默认)
    OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct")
    OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "")
    OPENROUTER_SITE_NAME = os.getenv("OPENROUTER_SITE_NAME", "Tea Order Agent")
    OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
    # vLLM 备选（Modal）
    VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "")
    VLLM_API_KEY = os.getenv("VLLM_API_KEY", "")
    VLLM_MODEL = os.getenv("VLLM_MODEL", OPENROUTER_MODEL)

    # Session
    MAX_HISTORY_LENGTH = 10  # 最多保存 10 轮对话


config = Config()
