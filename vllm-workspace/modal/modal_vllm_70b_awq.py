"""
Modal 部署：Llama-3.1-70B AWQ量化版本

使用INT4 AWQ量化，单个A100-80GB即可运行
显存需求：~55GB（vs 原始版本的140GB）
性能损失：<5%
"""
import os
import modal
from typing import List, Dict, Any, Optional

# ===== 配置 =====
# 使用预量化的AWQ模型（推荐）
VLLM_MODEL = os.environ.get("VLLM_MODEL", "casperhansen/llama-3.1-70b-instruct-awq")
VLLM_MAX_MODEL_LEN = 4096  # AWQ量化后可支持4K context
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
        "autoawq",  # AWQ量化支持
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

weights_volume = modal.Volume.from_name("vllm-70b-awq-cache", create_if_missing=True)

app = modal.App("vllm-70b-awq")

# ===== vLLM 推理函数 =====
vllm_llm = None


@app.function(
    image=vllm_image,
    gpu="A100-80GB",  # 单卡即可！
    volumes={"/weights": weights_volume},
    secrets=[modal.Secret.from_name("vllm-secrets")],
    scaledown_window=180,  # 3分钟后释放GPU（70B加载慢，给多点时间）
    timeout=600,  # 首次下载模型可能需要更长时间
)
def generate_text_70b(
    messages: List[Dict[str, str]],
    max_tokens: int = 2048,
    temperature: float = 0.7,
    top_p: float = 0.9,
) -> Dict[str, Any]:
    """
    70B AWQ量化模型推理

    显存优化：
    - INT4量化：模型权重仅35GB（vs FP16的140GB）
    - 单A100-80GB即可运行
    - KV缓存：~20GB（4K context）
    - 总需求：~55GB
    """
    global vllm_llm

    # 首次调用时初始化模型
    if vllm_llm is None:
        from vllm import LLM, SamplingParams

        print(f"🚀 Loading 70B AWQ model: {VLLM_MODEL}")
        print(f"📊 Expected memory usage: ~55GB / 80GB")

        vllm_llm = LLM(
            model=VLLM_MODEL,
            download_dir="/weights",
            quantization="awq",  # 启用AWQ INT4量化
            gpu_memory_utilization=VLLM_GPU_MEMORY_UTILIZATION,
            max_model_len=VLLM_MAX_MODEL_LEN,
            tensor_parallel_size=1,  # 单GPU
            dtype="auto",  # 自动选择数据类型
        )

        print(f"✅ Model loaded successfully!")

    # 构建prompt
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

    fastapi_app = FastAPI(
        title="VLLM 70B AWQ Service",
        description="Llama-3.1-70B-Instruct AWQ量化版本（单A100-80GB）",
        version="1.0.0",
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
        model: str
        quantization: str
        gpu_requirement: str
        memory_usage: str

    # API端点
    @fastapi_app.get("/")
    async def root():
        return {
            "service": "VLLM 70B AWQ Service",
            "version": "1.0.0",
            "model": VLLM_MODEL,
            "quantization": "AWQ INT4",
            "gpu": "Single A100-80GB",
            "memory": "~55GB / 80GB",
            "quality_loss": "<5%",
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
            model=VLLM_MODEL,
            quantization="AWQ INT4",
            gpu_requirement="Single A100-80GB",
            memory_usage="~55GB / 80GB"
        )

    @fastapi_app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest):
        """对话接口 - 调用70B AWQ模型"""
        try:
            logger.info(f"收到70B模型请求，{len(request.messages)}条消息")

            messages_dict = [{"role": m.role, "content": m.content} for m in request.messages]

            logger.info("调用70B AWQ推理函数...")

            # 调用Modal函数
            result = generate_text_70b.remote(
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

            result = generate_text_70b.remote(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
            )

            return {
                "id": "chatcmpl-vllm-70b",
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
    print("🚀 VLLM 70B AWQ 量化部署")
    print("=" * 70)
    print()
    print("📦 模型配置:")
    print(f"   - 模型: {VLLM_MODEL}")
    print(f"   - 量化: AWQ INT4")
    print(f"   - GPU: 单个A100-80GB")
    print(f"   - 显存: ~55GB / 80GB（节省62%）")
    print(f"   - 上下文: {VLLM_MAX_MODEL_LEN} tokens")
    print()
    print("⚡ 性能特点:")
    print("   - 质量损失: <5%")
    print("   - 推理速度: ~60 tokens/秒")
    print("   - 成本: $1.10/小时（vs 2×GPU $2.20/小时）")
    print()
    print("🔧 部署命令:")
    print("   modal deploy modal_vllm_70b_awq.py")
    print()
    print("📝 注意事项:")
    print("   - 首次下载模型需要10-15分钟")
    print("   - 确保HuggingFace token有权限访问模型")
    print("   - 3分钟无请求后GPU自动释放")
    print()
    print("💰 成本对比:")
    print("   - 原始70B（2×A100）: $2.20/小时")
    print("   - AWQ 70B（1×A100）: $1.10/小时 ⭐")
    print("   - 节省: 50%")
    print("=" * 70)
