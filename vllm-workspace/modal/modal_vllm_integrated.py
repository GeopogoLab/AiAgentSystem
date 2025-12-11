"""
Modal 集成部署：vLLM + FastAPI Wrapper

将vLLM服务器和FastAPI包装层部署在同一个容器中，
避免冷启动问题，保持服务持续运行。
"""
import os
import subprocess
import time
import signal
from pathlib import Path
import modal

# ===== 配置 =====
# vLLM 配置
VLLM_MODEL = os.environ.get("VLLM_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
VLLM_PORT = 8000
VLLM_MAX_MODEL_LEN = os.environ.get("VLLM_MAX_MODEL_LEN", "8192")
VLLM_GPU_MEMORY_UTILIZATION = os.environ.get("VLLM_GPU_MEMORY_UTILIZATION", "0.90")
VLLM_TENSOR_PARALLEL = int(os.environ.get("VLLM_TENSOR_PARALLEL", "1"))  # 8B模型单GPU即可

# FastAPI Wrapper 配置
WRAPPER_PORT = 8001

# GPU 配置
GPU_TYPE = os.environ.get("VLLM_GPU_TYPE", "A100-80GB")
GPU_COUNT = int(os.environ.get("VLLM_GPU_COUNT", "1"))  # 8B模型单GPU足够

# 超时配置
CONTAINER_IDLE_TIMEOUT = 30 * 60  # 30分钟无请求后休眠

# ===== Modal 镜像 =====
# 集成镜像：包含vLLM和FastAPI依赖
integrated_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "curl")
    .pip_install(
        # vLLM 依赖 (vllm requires pydantic>=2.9)
        "vllm==0.6.6.post1",
        "torch==2.5.1",
        "transformers==4.46.0",
        "hf-transfer",
        # FastAPI 依赖 (compatible versions)
        "fastapi>=0.109.0",
        "uvicorn[standard]>=0.27.0",
        "pydantic>=2.9",
        "openai>=1.54.0",
        "httpx>=0.27.0",
    )
)

# 模型缓存卷
weights_volume = modal.Volume.from_name("vllm-llama70b-cache", create_if_missing=True)

# Modal App
app = modal.App("vllm-integrated")


# ===== FastAPI Wrapper 代码（内联版本）=====
WRAPPER_CODE = """
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
VLLM_BASE_URL = "http://localhost:8000/v1"
VLLM_MODEL = os.getenv("VLLM_MODEL", "meta-llama/Llama-3.1-70B-Instruct")
VLLM_API_KEY = os.getenv("VLLM_SERVER_API_KEY", "")
SERVICE_API_KEY = os.getenv("VLLM_WRAPPER_API_KEY", "")

DEFAULT_MAX_TOKENS = 2048
DEFAULT_TEMPERATURE = 0.7

# ===== 请求/响应模型 =====
class Message(BaseModel):
    role: str = Field(..., description="角色: user, assistant, system")
    content: str = Field(..., description="消息内容")

class ChatRequest(BaseModel):
    messages: List[Message] = Field(..., description="对话历史")
    max_tokens: Optional[int] = Field(None, description="最大生成token数")
    temperature: Optional[float] = Field(None, description="温度参数 (0-2)")
    top_p: Optional[float] = Field(None, description="Top-p采样参数")
    stream: bool = Field(False, description="是否流式返回")
    model: Optional[str] = Field(None, description="模型名称（可选）")

class ChatResponse(BaseModel):
    content: str = Field(..., description="回复内容")
    model: str = Field(..., description="使用的模型")
    usage: Optional[Dict[str, int]] = Field(None, description="Token使用统计")
    finish_reason: Optional[str] = Field(None, description="结束原因")

class HealthResponse(BaseModel):
    status: str = Field(..., description="服务状态")
    vllm_available: bool = Field(..., description="VLLM是否可用")
    model: str = Field(..., description="配置的模型")

# ===== VLLM 客户端 =====
class VLLMClient:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=VLLM_BASE_URL,
            api_key=VLLM_API_KEY or "EMPTY",
            timeout=120.0
        )
        self.model = VLLM_MODEL
        logger.info(f"初始化VLLM客户端: {VLLM_BASE_URL}, 模型: {self.model}")

    async def health_check(self) -> bool:
        try:
            models = await self.client.models.list()
            logger.info(f"VLLM健康检查成功")
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
        params = {
            "model": model or self.model,
            "messages": messages,
            "max_tokens": max_tokens or DEFAULT_MAX_TOKENS,
            "temperature": temperature if temperature is not None else DEFAULT_TEMPERATURE,
            "stream": stream,
        }
        if top_p is not None:
            params["top_p"] = top_p

        try:
            response = await self.client.chat.completions.create(**params)
            return response
        except OpenAIError as e:
            logger.error(f"VLLM请求失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"VLLM服务调用失败: {str(e)}"
            )

# ===== FastAPI 应用 =====
vllm_client: Optional[VLLMClient] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global vllm_client
    logger.info("🚀 VLLM Wrapper 服务启动")

    # 等待vLLM服务就绪
    import asyncio
    max_retries = 30
    for i in range(max_retries):
        try:
            vllm_client = VLLMClient()
            if await vllm_client.health_check():
                logger.info("✅ VLLM 连接成功")
                break
        except Exception as e:
            if i < max_retries - 1:
                logger.info(f"等待vLLM启动... ({i+1}/{max_retries})")
                await asyncio.sleep(2)
            else:
                logger.warning("⚠️ VLLM 连接失败")

    yield
    logger.info("👋 VLLM Wrapper 服务关闭")

app = FastAPI(
    title="VLLM Integrated Service",
    description="集成vLLM和FastAPI的一体化服务",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== 认证 =====
def verify_api_key(authorization: Optional[str] = Header(None)):
    if not SERVICE_API_KEY:
        return True

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    token = authorization
    if authorization.startswith("Bearer "):
        token = authorization[7:]

    if token != SERVICE_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return True

# ===== API 端点 =====
@app.get("/")
async def root():
    return {
        "service": "VLLM Integrated Service",
        "version": "2.0.0",
        "status": "running",
        "model": VLLM_MODEL,
        "endpoints": {
            "POST /v1/chat/completions": "OpenAI兼容对话接口",
            "POST /chat": "简化对话接口",
            "GET /health": "健康检查",
            "GET /models": "列出模型"
        }
    }

@app.get("/health", response_model=HealthResponse)
async def health():
    if not vllm_client:
        return HealthResponse(
            status="starting",
            vllm_available=False,
            model=VLLM_MODEL
        )

    is_healthy = await vllm_client.health_check()
    return HealthResponse(
        status="healthy" if is_healthy else "degraded",
        vllm_available=is_healthy,
        model=VLLM_MODEL
    )

@app.get("/models")
async def list_models():
    if not vllm_client:
        raise HTTPException(status_code=503, detail="VLLM客户端未初始化")

    try:
        models = await vllm_client.client.models.list()
        return {"models": [{"id": m.id, "object": m.object} for m in models.data]}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"无法获取模型列表: {str(e)}")

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not vllm_client:
        raise HTTPException(status_code=503, detail="VLLM客户端未初始化")

    messages = [{"role": m.role, "content": m.content} for m in request.messages]

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
                        yield f"data: {chunk.choices[0].delta.content}\\n\\n"
                yield "data: [DONE]\\n\\n"
            except Exception as e:
                logger.error(f"流式响应错误: {e}")
                yield f"data: [ERROR] {str(e)}\\n\\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

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
async def openai_compatible_chat(request: Dict[str, Any]):
    if not vllm_client:
        raise HTTPException(status_code=503, detail="VLLM客户端未初始化")

    try:
        stream = request.get("stream", False)
        response = await vllm_client.chat(
            messages=request.get("messages", []),
            max_tokens=request.get("max_tokens"),
            temperature=request.get("temperature"),
            top_p=request.get("top_p"),
            stream=stream,
            model=request.get("model")
        )

        if stream:
            async def generate():
                try:
                    async for chunk in response:
                        import json
                        yield f"data: {json.dumps(chunk.model_dump())}\\n\\n"
                    yield "data: [DONE]\\n\\n"
                except Exception as e:
                    logger.error(f"流式响应错误: {e}")

            return StreamingResponse(generate(), media_type="text/event-stream")

        return response.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"对话请求失败: {e}")
        raise HTTPException(status_code=500, detail=f"处理请求时出错: {str(e)}")
"""


@app.function(
    image=integrated_image,
    gpu="A100-80GB",  # 单个A100 GPU for 8B model
    timeout=24 * 3600,  # 24小时超时
    scaledown_window=CONTAINER_IDLE_TIMEOUT,  # 30分钟无请求后休眠
    volumes={"/weights": weights_volume},
    secrets=[modal.Secret.from_name("vllm-secrets")],
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def serve():
    """
    启动集成服务：在同一个容器中运行vLLM和FastAPI Wrapper

    架构：
    1. 后台启动vLLM服务器 (localhost:8000)
    2. 启动FastAPI Wrapper (监听外部请求)
    3. FastAPI通过localhost调用vLLM，无网络延迟
    """
    import sys
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # 准备环境变量
    env = os.environ.copy()
    hf_token = env.get("HUGGING_FACE_HUB_TOKEN") or env.get("HF_TOKEN")
    if hf_token:
        env["HUGGING_FACE_HUB_TOKEN"] = hf_token

    # 设置vLLM模型环境变量供wrapper使用
    env["VLLM_MODEL"] = VLLM_MODEL

    # 1. 在后台启动vLLM服务器
    logger.info("=" * 60)
    logger.info("🚀 启动集成服务")
    logger.info("=" * 60)
    logger.info(f"📦 模型: {VLLM_MODEL}")
    logger.info(f"🎮 GPU: {GPU_TYPE} x {GPU_COUNT}")
    logger.info(f"💾 最大长度: {VLLM_MAX_MODEL_LEN} tokens")
    logger.info(f"🔧 显存利用率: {VLLM_GPU_MEMORY_UTILIZATION}")
    logger.info("=" * 60)

    vllm_command = [
        "python3", "-m", "vllm.entrypoints.openai.api_server",
        "--model", VLLM_MODEL,
        "--port", str(VLLM_PORT),
        "--host", "0.0.0.0",
        "--download-dir", "/weights",
        "--tensor-parallel-size", str(VLLM_TENSOR_PARALLEL),
        "--gpu-memory-utilization", str(VLLM_GPU_MEMORY_UTILIZATION),
        "--max-model-len", str(VLLM_MAX_MODEL_LEN),
    ]

    # 添加API Key（如果配置了）
    server_api_key = env.get("VLLM_SERVER_API_KEY")
    if server_api_key:
        vllm_command.extend(["--api-key", server_api_key])

    logger.info(f"🔨 启动vLLM服务器: {' '.join(vllm_command)}")

    # 后台启动vLLM
    vllm_process = subprocess.Popen(
        vllm_command,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    # 2. 等待vLLM服务器就绪
    logger.info("⏳ 等待vLLM服务器启动...")
    max_wait = 300  # 5分钟
    waited = 0
    vllm_ready = False

    # 在后台线程中读取vLLM输出
    import threading
    def log_vllm_output():
        for line in vllm_process.stdout:
            print(f"[vLLM] {line.rstrip()}", flush=True)

    log_thread = threading.Thread(target=log_vllm_output, daemon=True)
    log_thread.start()

    # 检查vLLM是否就绪
    while waited < max_wait:
        try:
            import httpx
            response = httpx.get(f"http://localhost:{VLLM_PORT}/health", timeout=5.0)
            if response.status_code == 200:
                vllm_ready = True
                logger.info("✅ vLLM服务器已就绪")
                break
        except Exception:
            pass

        time.sleep(5)
        waited += 5
        if waited % 30 == 0:
            logger.info(f"   仍在等待... ({waited}s / {max_wait}s)")

    if not vllm_ready:
        logger.error("❌ vLLM服务器启动超时")
        vllm_process.kill()
        raise RuntimeError("vLLM服务器启动失败")

    # 3. 创建并返回FastAPI应用
    logger.info("🌐 启动FastAPI Wrapper...")

    # 将wrapper代码写入临时文件
    wrapper_file = Path("/tmp/wrapper_app.py")
    wrapper_file.write_text(WRAPPER_CODE)

    # 导入FastAPI应用
    sys.path.insert(0, "/tmp")
    from wrapper_app import app as fastapi_app

    logger.info("=" * 60)
    logger.info("✅ 集成服务启动完成！")
    logger.info("=" * 60)
    logger.info(f"🔗 vLLM服务: http://localhost:{VLLM_PORT}")
    logger.info(f"🔗 FastAPI服务: 监听Modal外部端口")
    logger.info(f"⏱️  闲置超时: {CONTAINER_IDLE_TIMEOUT // 60} 分钟")
    logger.info("=" * 60)

    return fastapi_app


@app.local_entrypoint()
def main():
    """本地入口"""
    print("=" * 70)
    print("🚀 VLLM 集成部署 - 将vLLM和FastAPI部署在同一容器中")
    print("=" * 70)
    print()
    print("📦 配置:")
    print(f"   - 模型: {VLLM_MODEL}")
    print(f"   - GPU: {GPU_TYPE} x {GPU_COUNT}")
    print(f"   - Tensor Parallel: {VLLM_TENSOR_PARALLEL}")
    print(f"   - 最大上下文: {VLLM_MAX_MODEL_LEN} tokens")
    print(f"   - 显存利用率: {VLLM_GPU_MEMORY_UTILIZATION}")
    print(f"   - 闲置超时: {CONTAINER_IDLE_TIMEOUT // 60} 分钟")
    print()
    print("🔧 部署命令:")
    print("   modal deploy modal_vllm_integrated.py")
    print()
    print("📝 需要配置 Modal Secret 'vllm-secrets':")
    print("   - HUGGING_FACE_HUB_TOKEN: Hugging Face访问令牌（必需）")
    print("   - VLLM_SERVER_API_KEY: vLLM服务API密钥（可选）")
    print("   - VLLM_WRAPPER_API_KEY: Wrapper服务API密钥（可选）")
    print()
    print("✨ 优势:")
    print("   ✓ 无冷启动问题（vLLM在容器内常驻）")
    print("   ✓ 无网络延迟（localhost通信）")
    print("   ✓ 30分钟无请求后自动休眠节省成本")
    print("   ✓ 统一管理和部署")
    print()
    print("📡 部署后的端点:")
    print("   - POST /v1/chat/completions - OpenAI兼容接口")
    print("   - POST /chat - 简化对话接口")
    print("   - GET /health - 健康检查")
    print("   - GET /models - 列出模型")
    print("=" * 70)
