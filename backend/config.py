"""配置文件"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class Config:
    """应用配置"""

    # API Keys
    ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # Database
    DATABASE_PATH = os.getenv("DATABASE_PATH", "./tea_orders.db")

    # Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))

    # AssemblyAI
    ASSEMBLYAI_API_URL = "https://api.assemblyai.com/v2"

    # OpenAI
    OPENAI_MODEL = "gpt-4"  # 或 "gpt-3.5-turbo" 节省成本
    OPENAI_TEMPERATURE = 0.7

    # Session
    MAX_HISTORY_LENGTH = 10  # 最多保存 10 轮对话

    # Upload
    UPLOAD_DIR = "./uploads"
    MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB


config = Config()
