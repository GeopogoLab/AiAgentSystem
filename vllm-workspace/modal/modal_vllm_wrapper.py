"""
VLLM Wrapper FastAPI 服务的 Modal 部署配置

提供一个包装层，简化VLLM的调用接口
可以部署在Modal上作为独立服务
"""
import modal

# Modal 镜像配置
vllm_wrapper_image = (
    modal.Image.debian_slim(python_version="3.10")
    .pip_install(
        "fastapi==0.109.0",
        "uvicorn[standard]==0.27.0",
        "pydantic==2.5.3",
        "openai==1.54.0",
        "httpx==0.27.0",
    )
)

# Modal App
app = modal.App("vllm-wrapper")


@app.function(
    image=vllm_wrapper_image,
    secrets=[modal.Secret.from_name("vllm-secrets")],
    timeout=24 * 3600,
    container_idle_timeout=15 * 60,
)
@modal.asgi_app()
def fastapi_app():
    """部署VLLM Wrapper FastAPI服务"""
    import os

    # 从 Modal Secret 读取配置
    os.environ.setdefault("VLLM_BASE_URL", os.getenv("VLLM_BASE_URL", ""))
    os.environ.setdefault("VLLM_MODEL", os.getenv("VLLM_MODEL", "meta-llama/Llama-3.1-70B-Instruct"))
    os.environ.setdefault("VLLM_API_KEY", os.getenv("VLLM_API_KEY", ""))
    os.environ.setdefault("VLLM_WRAPPER_API_KEY", os.getenv("VLLM_WRAPPER_API_KEY", ""))

    # 导入应用
    from vllm_wrapper import app as fastapi_application

    return fastapi_application


@app.local_entrypoint()
def main():
    """本地入口提示"""
    print("🚀 VLLM Wrapper - Modal 部署")
    print("=" * 50)
    print("部署命令: modal deploy modal_vllm_wrapper.py")
    print("")
    print("需要在 Modal Secret 'vllm-secrets' 中配置:")
    print("  - VLLM_BASE_URL: VLLM服务地址")
    print("  - VLLM_MODEL: 模型名称")
    print("  - VLLM_API_KEY: VLLM API密钥（可选）")
    print("  - VLLM_WRAPPER_API_KEY: 包装服务API密钥（可选）")
    print("")
    print("部署后可以通过以下端点访问:")
    print("  - POST /chat - 简化对话接口")
    print("  - POST /v1/chat/completions - OpenAI兼容接口")
    print("  - GET /health - 健康检查")
    print("  - GET /models - 列出模型")
