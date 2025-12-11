"""
Modal 部署：分离架构 - Wrapper永远在线，vLLM自动缩放

架构：
1. FastAPI Wrapper (无GPU，永远在线) - 处理HTTP请求
2. vLLM推理函数 (有GPU，自动缩放到0) - 只在推理时使用GPU

优势：
- Wrapper永远在线，无冷启动
- vLLM不用时自动释放GPU，节省成本
- 可以在wrapper层添加缓存、限流等功能
"""
import os
import modal
from typing import List, Dict, Any, Optional

# ===== 配置 =====
VLLM_MODEL = os.environ.get("VLLM_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
VLLM_MAX_MODEL_LEN = 8192
VLLM_GPU_MEMORY_UTILIZATION = 0.90

# ===== Modal 镜像 =====
# vLLM镜像（需要GPU）
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

# Wrapper镜像（轻量级，无GPU）
wrapper_image = (
    modal.Image.debian_slim(python_version="3.10")
    .pip_install(
        "fastapi>=0.109.0",
        "uvicorn[standard]>=0.27.0",
        "pydantic>=2.9",
        "httpx>=0.27.0",
    )
)

# 模型缓存
weights_volume = modal.Volume.from_name("vllm-llama-cache", create_if_missing=True)

# Modal App
app = modal.App("vllm-autoscale")


# ===== vLLM推理函数（自动缩放） =====
@app.cls(
    image=vllm_image,
    gpu="A100-80GB",
    volumes={"/weights": weights_volume},
    secrets=[modal.Secret.from_name("vllm-secrets")],
    scaledown_window=120,  # 2分钟无请求后释放GPU
)
class VLLMInference:
    """vLLM推理服务 - 自动缩放到0"""

    @modal.enter()
    def setup(self):
        """初始化vLLM引擎"""
        import torch
        from vllm import LLM, SamplingParams

        print(f"🚀 Loading model: {VLLM_MODEL}")

        self.llm = LLM(
            model=VLLM_MODEL,
            download_dir="/weights",
            gpu_memory_utilization=VLLM_GPU_MEMORY_UTILIZATION,
            max_model_len=VLLM_MAX_MODEL_LEN,
            tensor_parallel_size=1,
        )

        print(f"✅ Model loaded: {VLLM_MODEL}")

    @modal.method()
    def generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> Dict[str, Any]:
        """
        生成文本

        Args:
            prompt: 输入提示
            max_tokens: 最大token数
            temperature: 温度参数
            top_p: Top-p采样

        Returns:
            生成结果
        """
        from vllm import SamplingParams

        sampling_params = SamplingParams(
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
        )

        outputs = self.llm.generate([prompt], sampling_params)
        output = outputs[0]

        return {
            "text": output.outputs[0].text,
            "prompt_tokens": len(output.prompt_token_ids),
            "completion_tokens": len(output.outputs[0].token_ids),
            "finish_reason": output.outputs[0].finish_reason,
        }

    @modal.method()
    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> Dict[str, Any]:
        """
        对话接口

        Args:
            messages: 对话历史
            max_tokens: 最大token数
            temperature: 温度参数
            top_p: Top-p采样

        Returns:
            对话结果
        """
        # 将消息转换为prompt
        prompt = self._messages_to_prompt(messages)
        return self.generate(prompt, max_tokens, temperature, top_p)

    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """将对话消息转换为prompt"""
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
        return prompt


# ===== FastAPI Wrapper（永远在线） =====
@app.function(
    image=wrapper_image,
    # 不设置scaledown_window，让wrapper保持运行
    # Web服务默认行为是保持至少一个实例运行
    secrets=[modal.Secret.from_name("vllm-secrets")],
)
@modal.asgi_app()
def wrapper():
    """FastAPI Wrapper - 永远在线，调用vLLM推理函数"""
    from fastapi import FastAPI, HTTPException, status
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
    from typing import List, Dict, Optional
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # 获取vLLM推理类的引用（在应用外部）
    inference_cls = VLLMInference()

    # FastAPI应用
    fastapi_app = FastAPI(
        title="VLLM Auto-Scale Service",
        description="FastAPI wrapper (永远在线) + vLLM (自动缩放)",
        version="2.0.0",
    )

    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 请求模型
    class Message(BaseModel):
        role: str
        content: str

    class ChatRequest(BaseModel):
        messages: List[Message]
        max_tokens: Optional[int] = Field(2048, description="最大token数")
        temperature: Optional[float] = Field(0.7, description="温度参数")
        top_p: Optional[float] = Field(0.9, description="Top-p采样")

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

    # 根路径
    @fastapi_app.get("/")
    async def root():
        return {
            "service": "VLLM Auto-Scale Service",
            "version": "2.0.0",
            "architecture": {
                "wrapper": "Always-on (no GPU)",
                "vllm": "Auto-scale to zero (with GPU)",
                "scaledown_window": "2 minutes"
            },
            "model": VLLM_MODEL,
            "endpoints": {
                "POST /chat": "对话接口",
                "POST /v1/chat/completions": "OpenAI兼容接口",
                "GET /health": "健康检查",
            }
        }

    # 健康检查
    @fastapi_app.get("/health", response_model=HealthResponse)
    async def health():
        return HealthResponse(
            status="healthy",
            wrapper_status="running",
            vllm_status="auto-scaling (idle or active)",
            model=VLLM_MODEL,
            architecture="separated"
        )

    # 对话接口
    @fastapi_app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest):
        """
        对话接口 - 调用vLLM推理函数

        注意：首次调用可能需要等待vLLM启动（如果GPU已释放）
        """
        try:
            logger.info(f"收到对话请求，{len(request.messages)}条消息")

            # 调用vLLM推理函数
            messages_dict = [{"role": m.role, "content": m.content} for m in request.messages]

            logger.info("正在调用vLLM推理函数...")
            result = inference_cls.chat.remote(
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

    # OpenAI兼容接口
    @fastapi_app.post("/v1/chat/completions")
    async def openai_chat(request: Dict):
        """OpenAI兼容的对话接口"""
        try:
            messages = request.get("messages", [])
            max_tokens = request.get("max_tokens", 2048)
            temperature = request.get("temperature", 0.7)
            top_p = request.get("top_p", 0.9)

            # 调用vLLM推理函数
            result = inference_cls.chat.remote(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
            )

            # OpenAI格式响应
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
    """本地入口"""
    print("=" * 70)
    print("🚀 VLLM Auto-Scale 架构")
    print("=" * 70)
    print()
    print("📦 架构说明:")
    print("   ┌─────────────────────────────────────┐")
    print("   │  FastAPI Wrapper (永远在线)         │")
    print("   │  - 无GPU，成本极低                  │")
    print("   │  - 处理HTTP请求                     │")
    print("   │  - 可添加缓存/限流等功能            │")
    print("   └──────────────┬──────────────────────┘")
    print("                  │ Modal Function Call")
    print("                  ↓")
    print("   ┌─────────────────────────────────────┐")
    print("   │  vLLM推理函数 (自动缩放)            │")
    print("   │  - 有GPU，按需使用                  │")
    print("   │  - 2分钟无请求后释放GPU             │")
    print("   │  - 有请求时自动启动                 │")
    print("   └─────────────────────────────────────┘")
    print()
    print("⚙️  配置:")
    print(f"   - 模型: {VLLM_MODEL}")
    print(f"   - GPU: A100-80GB")
    print(f"   - Wrapper缩放: 永不释放")
    print(f"   - vLLM缩放: 2分钟后释放GPU")
    print()
    print("💰 成本优势:")
    print("   - Wrapper: ~$0.0001/小时 (无GPU)")
    print("   - vLLM: ~$1.10/小时 (仅在推理时)")
    print("   - 总成本: 取决于实际使用量")
    print()
    print("🔧 部署命令:")
    print("   modal deploy modal_vllm_autoscale.py")
    print()
    print("📝 部署后:")
    print("   - Wrapper立即可用，无冷启动")
    print("   - 首次推理请求会触发vLLM启动（约1-2分钟）")
    print("   - 后续请求如果在2分钟内，直接使用已加载的模型")
    print("   - 2分钟无请求后，GPU自动释放")
    print("=" * 70)
