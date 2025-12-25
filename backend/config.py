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

    # gTTS Fallback Configuration
    TTS_PROVIDER = os.getenv("TTS_PROVIDER", "assemblyai")  # "assemblyai" or "gtts"
    GTTS_LANGUAGE = os.getenv("GTTS_LANGUAGE", "en")      # gTTS language
    GTTS_SLOW = os.getenv("GTTS_SLOW", "false").lower() == "true"  # Slow speech
    LOCAL_TTS_MODEL = os.getenv("LOCAL_TTS_MODEL", "tts_models/en/ljspeech/tacotron2-DDC")
    LOCAL_TTS_DEVICE = os.getenv("LOCAL_TTS_DEVICE", "cuda")
    LOCAL_TTS_SPEAKER = os.getenv("LOCAL_TTS_SPEAKER", "")
    LOCAL_TTS_FORMAT = os.getenv("LOCAL_TTS_FORMAT", "wav")

    # AssemblyAI Streaming STT（补充缺失参数）
    ASSEMBLYAI_STREAMING_URL = os.getenv(
        "ASSEMBLYAI_STREAMING_URL",
        "wss://api.assemblyai.com/v2/realtime/ws"
    )
    ASSEMBLYAI_STREAMING_SAMPLE_RATE = int(os.getenv("ASSEMBLYAI_STREAMING_SAMPLE_RATE", "16000"))
    ASSEMBLYAI_STREAMING_ENCODING = os.getenv("ASSEMBLYAI_STREAMING_ENCODING", "pcm_s16le")
    ASSEMBLYAI_STREAMING_MODEL = os.getenv("ASSEMBLYAI_STREAMING_MODEL", "best")
    ASSEMBLYAI_CONNECTION_TIMEOUT = float(os.getenv("ASSEMBLYAI_CONNECTION_TIMEOUT", "3.0"))

    # Whisper 备用 STT（Modal 部署）
    WHISPER_ENABLED = os.getenv("WHISPER_ENABLED", "true").lower() == "true"
    WHISPER_SERVICE_URL = os.getenv("WHISPER_SERVICE_URL", "")
    WHISPER_API_KEY = os.getenv("WHISPER_API_KEY", "")
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "medium")
    WHISPER_TIMEOUT = float(os.getenv("WHISPER_TIMEOUT", "10.0"))

    # LLM Provider (OpenRouter 默认)
    OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct")
    OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "")
    OPENROUTER_SITE_NAME = os.getenv("OPENROUTER_SITE_NAME", "Tea Order Agent")
    OPENROUTER_TIMEOUT = float(os.getenv("OPENROUTER_TIMEOUT", "5.0"))  # OpenRouter 超时阈值（秒）
    OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))

    # vLLM 备选（Modal 部署的 Llama 3.3 70B）
    VLLM_BASE_URL = os.getenv(
        "VLLM_BASE_URL",
        "https://ybpang-1--vllm-llama33-70b-int8-wrapper.modal.run/v1"
    )
    VLLM_API_KEY = os.getenv("VLLM_API_KEY", "")
    VLLM_MODEL = os.getenv("VLLM_MODEL", "meta-llama/Llama-3.3-70B-Instruct")
    VLLM_TIMEOUT = float(os.getenv("VLLM_TIMEOUT", "10.0"))  # vLLM 超时阈值（秒）

    # Session
    MAX_HISTORY_LENGTH = 10  # 最多保存 10 轮对话


config = Config()
