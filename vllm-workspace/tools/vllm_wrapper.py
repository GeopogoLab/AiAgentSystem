"""
VLLM FastAPI 包装服务
提供简化的对话接口，支持本地和Modal部署
"""
import os
import logging
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from openai import AsyncOpenAI, OpenAIError
import uvicorn

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ===== 配置 =====
class VLLMConfig:
    """VLLM 配置"""

    def __init__(self):
        # VLLM 后端配置
        self.VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
        self.VLLM_MODEL = os.getenv("VLLM_MODEL", "meta-llama/Llama-3.1-70B-Instruct")
        self.VLLM_API_KEY = os.getenv("VLLM_API_KEY", "")

        # 服务配置
        self.HOST = os.getenv("VLLM_WRAPPER_HOST", "0.0.0.0")
        self.PORT = int(os.getenv("VLLM_WRAPPER_PORT", "8001"))
        self.SERVICE_API_KEY = os.getenv("VLLM_WRAPPER_API_KEY", "")  # 可选的服务层API Key

        # 默认参数
        self.DEFAULT_MAX_TOKENS = int(os.getenv("VLLM_DEFAULT_MAX_TOKENS", "2048"))
        self.DEFAULT_TEMPERATURE = float(os.getenv("VLLM_DEFAULT_TEMPERATURE", "0.7"))

        # 重试配置
        self.MAX_RETRIES = int(os.getenv("VLLM_MAX_RETRIES", "3"))
        self.TIMEOUT = int(os.getenv("VLLM_TIMEOUT", "60"))


config = VLLMConfig()


# ===== 请求/响应模型 =====
class Message(BaseModel):
    """对话消息"""
    role: str = Field(..., description="角色: user, assistant, system")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    """对话请求"""
    messages: List[Message] = Field(..., description="对话历史")
    max_tokens: Optional[int] = Field(None, description="最大生成token数")
    temperature: Optional[float] = Field(None, description="温度参数 (0-2)")
    top_p: Optional[float] = Field(None, description="Top-p采样参数")
    stream: bool = Field(False, description="是否流式返回")
    model: Optional[str] = Field(None, description="模型名称（可选）")


class ChatResponse(BaseModel):
    """对话响应"""
    content: str = Field(..., description="回复内容")
    model: str = Field(..., description="使用的模型")
    usage: Optional[Dict[str, int]] = Field(None, description="Token使用统计")
    finish_reason: Optional[str] = Field(None, description="结束原因")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="服务状态")
    vllm_available: bool = Field(..., description="VLLM是否可用")
    model: str = Field(..., description="配置的模型")
    base_url: str = Field(..., description="VLLM服务地址")


# ===== VLLM 客户端 =====
class VLLMClient:
    """VLLM 客户端包装器"""

    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=config.VLLM_BASE_URL,
            api_key=config.VLLM_API_KEY or "EMPTY"
        )
        self.model = config.VLLM_MODEL
        logger.info(f"初始化VLLM客户端: {config.VLLM_BASE_URL}, 模型: {self.model}")

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            # 尝试列出模型
            models = await self.client.models.list()
            logger.info(f"VLLM健康检查成功，可用模型: {[m.id for m in models.data]}")
            return True
        except Exception as e:
            logger.error(f"VLLM健康检查失败: {e}")
            return False

    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        stream: bool = False,
        model: Optional[str] = None,
    ):
        """
        发送对话请求

        Args:
            messages: 对话历史
            max_tokens: 最大token数
            temperature: 温度参数
            top_p: Top-p参数
            stream: 是否流式返回
            model: 模型名称

        Returns:
            OpenAI ChatCompletion对象或流式迭代器
        """
        params = {
            "model": model or self.model,
            "messages": messages,
            "max_tokens": max_tokens or config.DEFAULT_MAX_TOKENS,
            "temperature": temperature if temperature is not None else config.DEFAULT_TEMPERATURE,
            "stream": stream,
        }

        if top_p is not None:
            params["top_p"] = top_p

        logger.info(f"发送VLLM请求: {len(messages)}条消息, stream={stream}")

        try:
            response = await self.client.chat.completions.create(**params)
            return response
        except OpenAIError as e:
            logger.error(f"VLLM请求失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"VLLM服务调用失败: {str(e)}"
            )
        except Exception as e:
            logger.error(f"未预期的错误: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"服务内部错误: {str(e)}"
            )


# ===== FastAPI 应用 =====
vllm_client: Optional[VLLMClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global vllm_client
    logger.info("🚀 VLLM Wrapper 服务启动")
    logger.info(f"📍 VLLM Base URL: {config.VLLM_BASE_URL}")
    logger.info(f"🤖 Model: {config.VLLM_MODEL}")

    # 初始化客户端
    vllm_client = VLLMClient()

    # 健康检查
    if await vllm_client.health_check():
        logger.info("✅ VLLM 连接成功")
    else:
        logger.warning("⚠️ VLLM 连接失败，服务将继续运行但可能无法正常响应")

    yield

    logger.info("👋 VLLM Wrapper 服务关闭")


app = FastAPI(
    title="VLLM Wrapper Service",
    description="VLLM 对话接口包装服务，支持本地和云端部署",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境建议配置具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== 认证中间件 =====
def verify_api_key(authorization: Optional[str] = Header(None)):
    """验证 API Key（如果配置了的话）"""
    if not config.SERVICE_API_KEY:
        # 未配置API Key，跳过验证
        return True

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )

    # 支持 "Bearer <token>" 格式
    token = authorization
    if authorization.startswith("Bearer "):
        token = authorization[7:]

    if token != config.SERVICE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )

    return True


# ===== API 端点 =====
@app.get("/")
async def root():
    """服务根路径"""
    return {
        "service": "VLLM Wrapper Service",
        "version": "1.0.0",
        "endpoints": {
            "POST /v1/chat/completions": "对话接口（OpenAI兼容格式）",
            "POST /chat": "简化对话接口",
            "GET /health": "健康检查",
            "GET /models": "列出可用模型"
        }
    }


@app.get("/health", response_model=HealthResponse)
async def health():
    """健康检查"""
    if not vllm_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VLLM客户端未初始化"
        )

    is_healthy = await vllm_client.health_check()

    return HealthResponse(
        status="healthy" if is_healthy else "degraded",
        vllm_available=is_healthy,
        model=config.VLLM_MODEL,
        base_url=config.VLLM_BASE_URL
    )


@app.get("/models")
async def list_models():
    """列出可用模型"""
    if not vllm_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VLLM客户端未初始化"
        )

    try:
        models = await vllm_client.client.models.list()
        return {
            "models": [{"id": m.id, "object": m.object} for m in models.data]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"无法获取模型列表: {str(e)}"
        )


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    _: bool = Header(None, alias="Authorization", include_in_schema=False, dependency=verify_api_key)
):
    """
    简化的对话接口

    支持流式和非流式响应
    """
    if not vllm_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VLLM客户端未初始化"
        )

    # 转换消息格式
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    # 流式响应
    if request.stream:
        async def generate():
            try:
                stream = await vllm_client.chat(
                    messages=messages,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                    top_p=request.top_p,
                    stream=True,
                    model=request.model
                )

                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        # SSE 格式
                        yield f"data: {content}\n\n"

                yield "data: [DONE]\n\n"

            except Exception as e:
                logger.error(f"流式响应错误: {e}")
                yield f"data: [ERROR] {str(e)}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream"
        )

    # 非流式响应
    response = await vllm_client.chat(
        messages=messages,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        top_p=request.top_p,
        stream=False,
        model=request.model
    )

    choice = response.choices[0]

    return ChatResponse(
        content=choice.message.content,
        model=response.model,
        usage=response.usage.model_dump() if response.usage else None,
        finish_reason=choice.finish_reason
    )


@app.post("/v1/chat/completions")
async def openai_compatible_chat(
    request: Dict[str, Any],
    _: bool = Header(None, alias="Authorization", include_in_schema=False, dependency=verify_api_key)
):
    """
    OpenAI 兼容的对话接口

    直接透传到VLLM，保持完全兼容性
    """
    if not vllm_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VLLM客户端未初始化"
        )

    try:
        # 直接转发请求到VLLM
        stream = request.get("stream", False)

        response = await vllm_client.chat(
            messages=request.get("messages", []),
            max_tokens=request.get("max_tokens"),
            temperature=request.get("temperature"),
            top_p=request.get("top_p"),
            stream=stream,
            model=request.get("model")
        )

        # 流式响应
        if stream:
            async def generate():
                try:
                    async for chunk in response:
                        import json
                        yield f"data: {json.dumps(chunk.model_dump())}\n\n"
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    logger.error(f"流式响应错误: {e}")

            return StreamingResponse(
                generate(),
                media_type="text/event-stream"
            )

        # 非流式响应
        return response.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"对话请求失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理请求时出错: {str(e)}"
        )


# ===== 本地运行入口 =====
if __name__ == "__main__":
    uvicorn.run(
        "vllm_wrapper:app",
        host=config.HOST,
        port=config.PORT,
        reload=True,
        log_level="info"
    )
