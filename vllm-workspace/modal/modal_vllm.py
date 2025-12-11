"""Modal 部署 vLLM：LLAMA 70B 备选服务（OpenRouter 回退）"""
import os
import subprocess
import modal

# 模型与运行参数
DEFAULT_MODEL = "meta-llama/Llama-3.1-70B-Instruct"
MODEL_ID = os.environ.get("VLLM_MODEL", DEFAULT_MODEL)
TENSOR_PARALLEL = os.environ.get("VLLM_TENSOR_PARALLEL", "1")
MAX_MODEL_LEN = os.environ.get("VLLM_MAX_MODEL_LEN", "8192")
GPU_MEMORY_UTILIZATION = os.environ.get("VLLM_GPU_MEMORY_UTILIZATION", "0.95")
SERVER_PORT = int(os.environ.get("VLLM_SERVER_PORT", "8000"))
SERVER_API_KEY = os.environ.get("VLLM_SERVER_API_KEY", os.environ.get("VLLM_API_KEY", ""))
GPU_COUNT = int(os.environ.get("VLLM_GPU_COUNT", "1"))

# 镜像：安装 vLLM 与依赖
vllm_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git")
    .pip_install(
        "vllm==0.6.6.post1",
        "torch==2.5.1",
        "transformers==4.46.0",
        "hf-transfer"
    )
)

# 模型缓存，避免重复下载
weights_volume = modal.Volume.from_name("vllm-llama70b-cache", create_if_missing=True)

# Modal App
app = modal.App("vllm-llama70b")


@app.function(
    image=vllm_image,
    gpu="A100-80GB",
    timeout=24 * 3600,
    scaledown_window=15 * 60,
    volumes={"/weights": weights_volume},
    secrets=[modal.Secret.from_name("vllm-secrets")],
)
@modal.concurrent(max_inputs=100)
@modal.web_server(port=SERVER_PORT)
def serve_vllm():
    """启动 vLLM OpenAI 兼容服务"""
    env = os.environ.copy()
    hf_token = env.get("HUGGING_FACE_HUB_TOKEN") or env.get("HF_TOKEN")
    if hf_token:
        env["HUGGING_FACE_HUB_TOKEN"] = hf_token

    command = [
        "python3",
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model",
        MODEL_ID,
        "--port",
        str(SERVER_PORT),
        "--host",
        "0.0.0.0",
        "--download-dir",
        "/weights",
        "--tensor-parallel-size",
        str(TENSOR_PARALLEL),
        "--gpu-memory-utilization",
        str(GPU_MEMORY_UTILIZATION),
        "--max-model-len",
        str(MAX_MODEL_LEN),
    ]

    if SERVER_API_KEY:
        command.extend(["--api-key", SERVER_API_KEY])

    subprocess.run(command, check=True, env=env)


@app.local_entrypoint()
def main():
    """本地提示"""
    print("vLLM 70B 备选模型 - Modal 配置")
    print("部署命令: modal deploy modal_vllm.py")
    print("默认模型:", MODEL_ID)
    print(f"GPU: A100-80G x {GPU_COUNT} (tensor_parallel={TENSOR_PARALLEL})")
    print(f"最大上下文长度: {MAX_MODEL_LEN} tokens")
    print(f"显存利用率: {GPU_MEMORY_UTILIZATION}")
    print("Secret 名称: vllm-secrets (可含 HUGGING_FACE_HUB_TOKEN / VLLM_SERVER_API_KEY)")
    print(f"模型缓存卷: vllm-llama70b-cache -> /weights")
