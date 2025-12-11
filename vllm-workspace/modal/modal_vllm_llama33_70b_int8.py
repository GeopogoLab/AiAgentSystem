"""
Modal 部署：Llama 3.3 70B (BF16/FP16) + Tensor Parallelism

使用Tensor Parallelism，2个A100-80GB运行
显存需求：每个GPU ~70GB（总共140GB分布式）
性能损失：0%（原始精度）

配置：
- 2个A100-80GB GPU (tensor_parallel_size=2)
- max_model_len=4096 (充足的context窗口)
- gpu_memory_utilization=0.90 (每个GPU分担一半负载)
- dtype=auto (BF16或FP16)
"""
import os
import modal
from typing import List, Dict, Any, Optional

# ===== 配置 =====
VLLM_MODEL = os.environ.get("VLLM_MODEL", "meta-llama/Llama-3.3-70B-Instruct")
VLLM_MAX_MODEL_LEN = 4096  # 使用2个GPU后可以提高context
VLLM_GPU_MEMORY_UTILIZATION = 0.90  # 2个GPU分担负载

# ===== Modal 镜像 =====
vllm_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git")
    .pip_install(
        "vllm==0.6.6.post1",
        "torch==2.5.1",
        "transformers==4.46.0",
        "hf-transfer",
        "bitsandbytes>=0.41.0",  # INT8量化支持
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

weights_volume = modal.Volume.from_name("vllm-llama33-70b-int8", create_if_missing=True)

app = modal.App("vllm-llama33-70b-int8")

# ===== vLLM 推理函数 =====
vllm_llm = None


@app.function(
    image=vllm_image,
    # 使用2个GPU进行tensor parallelism
    gpu="A100-80GB:2",  # 2个A100-80GB GPU
    volumes={"/weights": weights_volume},
    secrets=[modal.Secret.from_name("vllm-secrets")],
    scaledown_window=180,  # 3分钟后释放GPU
    timeout=900,  # 15分钟超时（首次下载模型较大）
)
def generate_text_70b_int8(
    messages: List[Dict[str, str]],
    max_tokens: int = 2048,
    temperature: float = 0.7,
    top_p: float = 0.9,
) -> Dict[str, Any]:
    """
    Llama 3.3 70B 推理 (Tensor Parallelism)

    Tensor Parallelism配置：
    - 精度：BF16/FP16（自动选择）
    - 模型权重：~140GB（分布式）
    - Tensor Parallelism: 模型分布到2个GPU
    - 每个GPU: ~70GB模型 + ~10-15GB KV缓存 = ~75-85GB
    - 总需求：2×A100-80GB = 160GB总显存

    GPU配置：
    - 2个A100-80GB (tensor_parallel_size=2)
    - 每个GPU负载~80-90%
    - 支持4K context窗口
    """
    global vllm_llm

    if vllm_llm is None:
        from vllm import LLM, SamplingParams
        import torch

        print(f"🚀 Loading Llama 3.3 70B with Tensor Parallelism")
        print(f"📦 Model: {VLLM_MODEL}")
        print(f"💾 Precision: BF16/FP16 (auto)")
        print(f"🎮 GPUs: 2×A100-80GB (tensor_parallel_size=2)")
        print(f"📊 Expected memory per GPU: ~70-85GB")
        print(f"🎯 Max context: {VLLM_MAX_MODEL_LEN} tokens")
        print(f"⚙️  GPU memory util: {VLLM_GPU_MEMORY_UTILIZATION}")

        # 检查GPU信息
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            total_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
            print(f"🎮 GPU: {gpu_name}")
            print(f"💾 Total VRAM: {total_memory:.1f}GB")

        vllm_llm = LLM(
            model=VLLM_MODEL,
            download_dir="/weights",
            # 不使用量化，依赖tensor parallelism分布模型
            # quantization="fp8",  # 暂时禁用，与tensor parallelism可能有冲突
            gpu_memory_utilization=VLLM_GPU_MEMORY_UTILIZATION,
            max_model_len=VLLM_MAX_MODEL_LEN,
            tensor_parallel_size=2,  # 2个GPU进行tensor parallelism
            dtype="auto",  # 自动选择最佳精度（通常是BF16或FP16）
            # 额外优化选项
            enforce_eager=False,  # 使用CUDA graphs加速
        )

        # 显示实际显存使用
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated(0) / 1e9
            reserved = torch.cuda.memory_reserved(0) / 1e9
            print(f"✅ Model loaded!")
            print(f"💾 Memory allocated: {allocated:.1f}GB")
            print(f"💾 Memory reserved: {reserved:.1f}GB")

    # 构建prompt（Llama 3.3格式）
    prompt = ""
    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if role == "system":
            prompt += f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{content}<|eot_id|>"
        elif role == "user":
            prompt += f"<|start_header_id|>user<|end_header_id|>\n\n{content}<|eot_id|>"
        elif role == "assistant":
            prompt += f"<|start_header_id|>assistant<|end_header_id|>\n\n{content}<|eot_id|>"

    prompt += "<|start_header_id|>assistant<|end_header_id|>\n\n"

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


# ===== FastAPI Wrapper =====
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
        title="Llama 3.3 70B INT8 Service",
        description="Meta Llama 3.3 70B Instruct with INT8 quantization",
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
        model_version: str
        quantization: str
        gpu_requirement: str
        context_length: int

    # API端点
    @fastapi_app.get("/")
    async def root():
        return {
            "service": "Llama 3.3 70B Service",
            "version": "1.0.0",
            "model": VLLM_MODEL,
            "model_version": "Llama 3.3 (Meta's latest)",
            "precision": "BF16/FP16 (auto)",
            "gpu": "2×A100-80GB (Tensor Parallelism)",
            "memory_per_gpu": "~70-85GB",
            "context_length": VLLM_MAX_MODEL_LEN,
            "quality_loss": "0% (original precision)",
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
            model_version="Llama 3.3",
            quantization="None (BF16/FP16 + Tensor Parallelism)",
            gpu_requirement="2×A100-80GB",
            context_length=VLLM_MAX_MODEL_LEN,
        )

    @fastapi_app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest):
        """对话接口"""
        try:
            logger.info(f"收到Llama 3.3 70B请求，{len(request.messages)}条消息")

            messages_dict = [{"role": m.role, "content": m.content} for m in request.messages]

            logger.info("调用Llama 3.3 70B INT8推理...")

            result = generate_text_70b_int8.remote(
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

            result = generate_text_70b_int8.remote(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
            )

            return {
                "id": "chatcmpl-llama33-70b",
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
    print("🚀 Llama 3.3 70B (BF16/FP16) + Tensor Parallelism 部署")
    print("=" * 70)
    print()
    print("📦 模型配置:")
    print(f"   - 模型: {VLLM_MODEL}")
    print(f"   - 版本: Llama 3.3 (Meta最新)")
    print(f"   - 精度: BF16/FP16 (auto，原始精度)")
    print(f"   - GPU: 2×A100-80GB (Tensor Parallelism)")
    print(f"   - 每GPU显存: ~70-85GB")
    print(f"   - 总显存: ~140-170GB (分布式)")
    print(f"   - 上下文长度: {VLLM_MAX_MODEL_LEN} tokens")
    print()
    print("⚡ 性能特点:")
    print("   - 质量损失: 0%（原始精度，无量化）")
    print("   - 推理速度: ~40-50 tokens/秒")
    print("   - 精度: 最高（BF16/FP16）")
    print("   - 可靠性: 高（tensor parallelism）")
    print()
    print("🎮 GPU配置:")
    print("   - 架构: Tensor Parallelism (模型切分)")
    print("   - GPUs: 2×A100-80GB")
    print("   - 每GPU负载: ~80-90%")
    print("   - tensor_parallel_size: 2")
    print()
    print("🔧 部署命令:")
    print("   modal deploy modal_vllm_llama33_70b_int8.py")
    print()
    print("📝 注意事项:")
    print("   - 首次下载Llama 3.3需要15-20分钟（模型较大）")
    print("   - 需要HuggingFace访问权限（Meta模型需申请）")
    print("   - 使用原始BF16/FP16精度（无量化）")
    print("   - tensor_parallel_size=2 确保模型分布到2个GPU")
    print()
    print("💰 成本:")
    print("   - 2×A100-80GB: ~$2.20/小时")
    print("   - 优势: 原始精度 + Tensor Parallelism + 高可靠性")
    print("=" * 70)
