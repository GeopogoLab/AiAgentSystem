"""Modal.com 部署配置"""
import modal

# 创建 Modal App
app = modal.App("tea-order-agent")

# 定义 Python 镜像和依赖
image = (
    modal.Image.debian_slim(python_version="3.10")
    .pip_install_from_requirements("requirements.txt")
)

# 创建持久化存储卷用于数据库
volume = modal.Volume.from_name("tea-orders-db", create_if_missing=True)

# 定义 Secrets（需要在 Modal 控制台配置）
# 在 Modal 控制台创建 Secret，名称为 "tea-agent-secrets"，包含以下环境变量：
# - ASSEMBLYAI_API_KEY
# - OPENROUTER_API_KEY
# - OPENROUTER_MODEL (可选)
# - ASSEMBLYAI_TTS_VOICE (可选)


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("tea-agent-secrets")],
    volumes={"/data": volume},
    timeout=3600,  # 1 小时超时
    container_idle_timeout=300,  # 5 分钟空闲超时
    allow_concurrent_inputs=100,  # 支持 100 个并发请求
)
@modal.asgi_app()
def fastapi_app():
    """启动 FastAPI 应用"""
    import os

    # 设置数据库路径到持久化存储卷
    os.environ["DATABASE_PATH"] = "/data/tea_orders.db"

    # 导入 FastAPI app
    from backend.main import app as fastapi_application

    return fastapi_application


# 本地运行时的入口点
@app.local_entrypoint()
def main():
    """本地测试入口"""
    print("Tea Order Agent System - Modal Deployment")
    print("部署命令: modal deploy modal_app.py")
    print("查看日志: modal app logs tea-order-agent")
    print("\n确保已在 Modal 控制台创建名为 'tea-agent-secrets' 的 Secret")
    print("包含以下环境变量:")
    print("  - ASSEMBLYAI_API_KEY")
    print("  - OPENROUTER_API_KEY")
    print("  - OPENROUTER_MODEL (可选)")
