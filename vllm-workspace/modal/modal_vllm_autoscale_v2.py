"""
Modal 部署：分离架构V2 - 使用函数而非类

使用函数更简单，更容易从ASGI应用中调用
"""
import os
import modal
from typing import List, Dict, Any, Optional

# ===== 配置 =====
VLLM_MODEL = os.environ.get("VLLM_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
VLLM_MAX_MODEL_LEN = 8192
VLLM_GPU_MEMORY_UTILIZATION = 0.90

# ===== Modal 镜像 =====
vllm_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git")
    .pip_install(
        "vllm==0.6.6.post1",
        "torch==2.5.1",
        "transformers==4.46.0",
        "hf-transfer",
    )
)

wrapper_image = (
    modal.Image.debian_slim(python_version="3.10")
    .pip_install(
        "fastapi>=0.109.0",
        "uvicorn[standard]>=0.27.0",
        "pydantic>=2.9",
    )
)

weights_volume = modal.Volume.from_name("vllm-llama-cache", create_if_missing=True)

app = modal.App("vllm-autoscale-v2")

# ===== vLLM 推理函数（使用全局模型）=====
vllm_llm = None


@app.function(
    image=vllm_image,
    gpu="A100-80GB",
    volumes={"/weights": weights_volume},
    secrets=[modal.Secret.from_name("vllm-secrets")],
    scaledown_window=120,  # 2分钟后释放GPU
)
def generate_text(
    messages: List[Dict[str, str]],
    max_tokens: int = 2048,
    temperature: float = 0.7,
    top_p: float = 0.9,
) -> Dict[str, Any]:
    """
    vLLM推理函数 - 自动缩放

    Args:
        messages: 对话历史
        max_tokens: 最大token数
        temperature: 温度参数
        top_p: Top-p采样

    Returns:
        推理结果
    """
    global vllm_llm

    # 首次调用时初始化模型
    if vllm_llm is None:
        from vllm import LLM, SamplingParams

        print(f"🚀 Loading model: {VLLM_MODEL}")

        vllm_llm = LLM(
            model=VLLM_MODEL,
            download_dir="/weights",
            gpu_memory_utilization=VLLM_GPU_MEMORY_UTILIZATION,
            max_model_len=VLLM_MAX_MODEL_LEN,
            tensor_parallel_size=1,
        )

        print(f"✅ Model loaded: {VLLM_MODEL}")

    # 将消息转换为prompt
    prompt = ""
    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if role == "system":
            prompt += f"<|system|>\n{content}\n"
        elif role == "user":
            prompt += f"<|user|>\n{content}\n"
        elif role == "assistant":
            prompt += f"<|assistant|>\n{content}\n"

    prompt += "<|assistant|>\n"

    # 推理
    from vllm import SamplingParams

    sampling_params = SamplingParams(
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
    )

    outputs = vllm_llm.generate([prompt], sampling_params)
    output = outputs[0]

    return {
        "text": output.outputs[0].text,
        "prompt_tokens": len(output.prompt_token_ids),
        "completion_tokens": len(output.outputs[0].token_ids),
        "finish_reason": output.outputs[0].finish_reason,
    }


# ===== FastAPI Wrapper（永远在线）=====
@app.function(image=wrapper_image)
@modal.asgi_app()
def wrapper():
    """FastAPI Wrapper - 永远在线"""
    from fastapi import FastAPI, HTTPException, status
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
    from typing import List, Dict, Optional
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # FastAPI应用
    fastapi_app = FastAPI(
        title="VLLM Auto-Scale Service V2",
        description="使用函数式架构的自动缩放vLLM服务",
        version="2.1.0",
    )

    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 请求/响应模型
    class Message(BaseModel):
        role: str
        content: str

    class ChatRequest(BaseModel):
        messages: List[Message]
        max_tokens: Optional[int] = 2048
        temperature: Optional[float] = 0.7
        top_p: Optional[float] = 0.9

    class ChatResponse(BaseModel):
        content: str
        model: str
        usage: Dict[str, int]
        finish_reason: Optional[str] = None

    class HealthResponse(BaseModel):
        status: str
        wrapper_status: str
        vllm_status: str
        model: str
        architecture: str

    # API端点
    @fastapi_app.get("/")
    async def root():
        return {
            "service": "VLLM Auto-Scale Service V2",
            "version": "2.1.0",
            "architecture": {
                "wrapper": "Always-on (no GPU)",
                "vllm": "Auto-scale function (with GPU)",
                "scaledown_window": "2 minutes"
            },
            "model": VLLM_MODEL,
            "endpoints": {
                "POST /chat": "对话接口",
                "POST /v1/chat/completions": "OpenAI兼容接口",
                "GET /health": "健康检查",
            }
        }

    @fastapi_app.get("/health", response_model=HealthResponse)
    async def health():
        return HealthResponse(
            status="healthy",
            wrapper_status="running",
            vllm_status="auto-scaling (idle or active)",
            model=VLLM_MODEL,
            architecture="separated-function"
        )

    @fastapi_app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest):
        """对话接口"""
        try:
            logger.info(f"收到对话请求，{len(request.messages)}条消息")

            # 转换消息
            messages_dict = [{"role": m.role, "content": m.content} for m in request.messages]

            logger.info("调用vLLM推理函数...")

            # 调用Modal函数
            result = generate_text.remote(
                messages=messages_dict,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
            )

            logger.info("推理完成")

            return ChatResponse(
                content=result["text"],
                model=VLLM_MODEL,
                usage={
                    "prompt_tokens": result["prompt_tokens"],
                    "completion_tokens": result["completion_tokens"],
                    "total_tokens": result["prompt_tokens"] + result["completion_tokens"],
                },
                finish_reason=result["finish_reason"],
            )

        except Exception as e:
            logger.error(f"推理失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"推理失败: {str(e)}"
            )

    @fastapi_app.post("/v1/chat/completions")
    async def openai_chat(request: Dict):
        """OpenAI兼容接口"""
        try:
            messages = request.get("messages", [])
            max_tokens = request.get("max_tokens", 2048)
            temperature = request.get("temperature", 0.7)
            top_p = request.get("top_p", 0.9)

            # 调用Modal函数
            result = generate_text.remote(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
            )

            return {
                "id": "chatcmpl-vllm",
                "object": "chat.completion",
                "created": int(__import__("time").time()),
                "model": VLLM_MODEL,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": result["text"],
                    },
                    "finish_reason": result["finish_reason"],
                }],
                "usage": {
                    "prompt_tokens": result["prompt_tokens"],
                    "completion_tokens": result["completion_tokens"],
                    "total_tokens": result["prompt_tokens"] + result["completion_tokens"],
                }
            }

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"推理失败: {str(e)}"
            )

    return fastapi_app


@app.local_entrypoint()
def main():
    print("=" * 70)
    print("🚀 VLLM Auto-Scale V2 - 函数式架构")
    print("=" * 70)
    print(f"模型: {VLLM_MODEL}")
    print("架构: Wrapper (永远在线) + vLLM函数 (自动缩放)")
    print("部署命令: modal deploy modal_vllm_autoscale_v2.py")
    print("=" * 70)
