"""FastAPI 后端主服务"""
import os
import uuid
import asyncio
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import config
from .models import TalkResponse, OrderStatus, AgentAction
from .database import db
from .session_manager import session_manager
from .stt import stt_client
from .agent import tea_agent

# 创建 FastAPI 应用
app = FastAPI(
    title="Tea Order Agent System",
    description="奶茶点单 AI Agent 系统",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 确保上传目录存在
os.makedirs(config.UPLOAD_DIR, exist_ok=True)


@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    print("🚀 Tea Order Agent System 启动成功！")
    print(f"📊 数据库路径: {config.DATABASE_PATH}")
    print(f"📁 上传目录: {config.UPLOAD_DIR}")


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Tea Order Agent System API",
        "version": "1.0.0",
        "endpoints": {
            "POST /talk": "处理语音输入并返回 Agent 响应",
            "POST /text": "处理文本输入（测试用）",
            "GET /orders/{order_id}": "查询订单",
            "GET /orders": "查询所有订单",
            "GET /session/{session_id}": "查询会话状态",
            "POST /reset/{session_id}": "重置会话"
        }
    }


@app.post("/talk", response_model=TalkResponse)
async def talk(
    audio: UploadFile = File(...),
    session_id: str = Form(...)
):
    """
    处理语音输入的核心接口

    1. 上传音频文件
    2. AssemblyAI 转文本
    3. LLM Agent 处理
    4. 更新会话状态
    5. 必要时保存订单
    """
    try:
        # 1. 保存上传的音频文件
        file_extension = os.path.splitext(audio.filename)[1]
        temp_filename = f"{uuid.uuid4()}{file_extension}"
        temp_filepath = os.path.join(config.UPLOAD_DIR, temp_filename)

        with open(temp_filepath, "wb") as f:
            content = await audio.read()
            f.write(content)

        # 2. 使用 AssemblyAI 转录
        try:
            user_text = await stt_client.transcribe_file(temp_filepath)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"语音转文本失败: {str(e)}")
        finally:
            # 清理临时文件
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)

        if not user_text:
            raise HTTPException(status_code=400, detail="无法识别语音内容")

        # 3. 处理文本（与 /text 接口共用逻辑）
        return await _process_text(session_id, user_text)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@app.post("/text", response_model=TalkResponse)
async def text(session_id: str = Form(...), text: str = Form(...)):
    """
    处理文本输入（测试用，不需要语音）

    这个接口方便开发和测试，可以直接发送文本而不需要录音
    """
    return await _process_text(session_id, text)


async def _process_text(session_id: str, user_text: str) -> TalkResponse:
    """
    处理文本的核心逻辑（供 /talk 和 /text 共用）

    Args:
        session_id: 会话 ID
        user_text: 用户输入的文本

    Returns:
        TalkResponse
    """
    # 1. 获取会话状态
    session = session_manager.get_session(session_id)

    # 2. 调用 Agent 处理
    agent_response = await tea_agent.process(
        user_text=user_text,
        history=session.history,
        current_order_state=session.order_state
    )

    # 3. 更新会话历史
    session_manager.add_message(session_id, "user", user_text)
    session_manager.add_message(session_id, "assistant", agent_response.assistant_reply)

    # 4. 更新订单状态
    session_manager.update_order_state(session_id, agent_response.order_state)

    # 5. 根据 action 决定下一步
    order_id = None

    if agent_response.action == AgentAction.SAVE_ORDER:
        # 保存订单到数据库
        order_id = db.save_order(session_id, agent_response.order_state)
        session_manager.update_status(session_id, OrderStatus.SAVED)

        # 在回复中添加订单号
        agent_response.assistant_reply += f" 订单号：#{order_id}"

    elif agent_response.action == AgentAction.CONFIRM:
        session_manager.update_status(session_id, OrderStatus.CONFIRMING)
    else:
        session_manager.update_status(session_id, OrderStatus.COLLECTING)

    # 6. 返回响应
    return TalkResponse(
        assistant_reply=agent_response.assistant_reply,
        order_state=agent_response.order_state,
        order_status=session_manager.get_session(session_id).status,
        order_id=order_id
    )


@app.get("/orders/{order_id}")
async def get_order(order_id: int):
    """查询订单"""
    order = db.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order


@app.get("/orders")
async def get_all_orders(limit: int = 100):
    """查询所有订单"""
    orders = db.get_all_orders(limit)
    return {"orders": orders, "total": len(orders)}


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """查询会话状态"""
    session = session_manager.get_session(session_id)
    return session.model_dump()


@app.post("/reset/{session_id}")
async def reset_session(session_id: str):
    """重置会话（开始新订单）"""
    session_manager.reset_session(session_id)
    return {"message": "会话已重置", "session_id": session_id}


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "healthy"}


# 如果需要服务前端静态文件
# app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=True
    )
