"""FastAPI 后端主服务"""
import os
import uuid
import asyncio
from contextlib import asynccontextmanager
import json
import websockets
import httpx
import re
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from typing import Optional, Tuple

from .config import config
from .models import (
    SessionState,
    TalkResponse,
    OrderStatus,
    AgentAction,
    OrderProgressResponse,
    ProgressChatRequest,
    ProgressSessionChatRequest,
    ProgressChatResponse,
    ProgressHistoryResponse,
    ProgressSessionHistoryResponse,
    TTSRequest,
    TTSResponse,
)
from .database import db
from .session_manager import session_manager
from .stt import stt_client
from .agent import tea_agent
from .production import build_order_progress, build_queue_snapshot, find_progress_in_snapshot
from .progress_agent import progress_agent
from .pricing import calculate_order_total

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    print("🚀 Tea Order Agent System 启动成功！")
    print(f"📊 数据库路径: {config.DATABASE_PATH}")
    print(f"📁 上传目录: {config.UPLOAD_DIR}")
    yield


# 创建 FastAPI 应用
app = FastAPI(
    title="Tea Order Agent System",
    description="奶茶点单 AI Agent 系统",
    version="1.0.0",
    lifespan=lifespan
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

PROGRESS_KEYWORDS = [
    "进度",
    "多久",
    "完成了",
    "准备好",
    "order status",
    "how long",
    "ready yet",
    "progress",
    "queue",
    "取餐",
]


def _load_queue_snapshot(limit: int = 50, include_order: Optional[int] = None):
    orders = db.get_recent_orders(limit)
    if include_order and not any(order["id"] == include_order for order in orders):
        extra = db.get_order(include_order)
        if extra:
            orders.append(extra)
    return build_queue_snapshot(orders)


def _should_route_to_progress(text: str) -> bool:
    normalized = text.lower()
    return any(keyword in text for keyword in PROGRESS_KEYWORDS) or any(
        keyword in normalized for keyword in ["eta", "wait time", "status"]
    )


def _extract_order_id(text: str) -> Optional[int]:
    match = re.search(r"#?(\d+)", text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


async def _answer_progress_question(
    session_id: str,
    user_text: str,
    explicit_order_id: Optional[int] = None,
) -> Tuple[str, str, Optional[int], Optional[OrderProgressResponse]]:
    """执行制作进度查询"""
    session = session_manager.get_session(session_id)
    order_id = explicit_order_id or _extract_order_id(user_text) or session.last_order_id
    snapshot = _load_queue_snapshot(include_order=order_id if order_id else None)
    session_manager.add_progress_session_message(session_id, "user", user_text)

    progress = None
    if order_id:
        order = db.get_order(order_id)
        if not order:
            answer = f"未找到编号 #{order_id} 的订单，请确认订单号是否正确。"
            session_manager.add_progress_session_message(session_id, "assistant", answer, mode="offline")
            return answer, "offline", order_id, None
        progress = find_progress_in_snapshot(snapshot, order_id)
        if not progress:
            progress = build_order_progress(order)
        session_manager.add_progress_message(order_id, "user", user_text)

    answer, mode = await progress_agent.answer(user_text, progress, snapshot)
    session_manager.add_progress_session_message(session_id, "assistant", answer, mode=mode)
    if order_id and progress:
        session_manager.add_progress_message(order_id, "assistant", answer, mode=mode)

    return answer, mode, order_id, progress


async def _handle_progress_query(session_id: str, session: SessionState, user_text: str) -> TalkResponse:
    """处理进度询问"""
    answer, mode, order_id, _ = await _answer_progress_question(session_id, user_text)
    latest_session = session_manager.get_session(session_id)
    return TalkResponse(
        assistant_reply=answer,
        order_state=latest_session.order_state,
        order_status=latest_session.status,
        order_id=order_id,
        reply_mode=mode,
        order_total=latest_session.last_order_total,
    )


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


@app.get("/health")
async def health():
    """健康检查"""
    db_status = "ok"
    try:
        with db.get_connection() as conn:
            conn.execute("SELECT 1")
    except Exception as exc:
        db_status = f"error: {exc}"

    upload_dir_ready = os.path.isdir(config.UPLOAD_DIR)
    status = "healthy" if db_status == "ok" and upload_dir_ready else "degraded"

    return {
        "status": status,
        "database": db_status,
        "upload_dir_ready": upload_dir_ready
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
    session = session_manager.get_session(session_id)
    if _should_route_to_progress(user_text):
        return await _handle_progress_query(session_id, session, user_text)

    history_payload = [{"role": msg.role, "content": msg.content} for msg in session.history]
    agent_response = await tea_agent.process(
        user_text=user_text,
        history=history_payload,
        current_order_state=session.order_state
    )

    session_manager.add_message(session_id, "user", user_text)
    session_manager.add_message(session_id, "assistant", agent_response.assistant_reply, mode=agent_response.mode)

    session_manager.update_order_state(session_id, agent_response.order_state)
    current_session = session_manager.get_session(session_id)
    order_total = current_session.last_order_total
    order_id = None

    if agent_response.action == AgentAction.SAVE_ORDER:
        # 保存订单到数据库
        try:
            order_id = db.save_order(session_id, agent_response.order_state)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        session_manager.update_status(session_id, OrderStatus.SAVED)
        current_session.last_order_id = order_id
        total = calculate_order_total(agent_response.order_state)
        current_session.last_order_total = total
        order_total = total

        # 在回复中添加订单号
        agent_response.assistant_reply += f" 订单号：#{order_id}"

    elif agent_response.action == AgentAction.CONFIRM:
        session_manager.update_status(session_id, OrderStatus.CONFIRMING)
    else:
        session_manager.update_status(session_id, OrderStatus.COLLECTING)

    final_session = session_manager.get_session(session_id)
    order_total = final_session.last_order_total if final_session else order_total

    # 6. 返回响应
    return TalkResponse(
        assistant_reply=agent_response.assistant_reply,
        order_state=agent_response.order_state,
        order_status=final_session.status if final_session else session.status,
        order_id=order_id,
        reply_mode=agent_response.mode,
        order_total=order_total,
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


@app.get("/orders/{order_id}/status", response_model=OrderProgressResponse)
async def get_order_status(order_id: int):
    """查询订单制作进度"""
    order = db.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    snapshot = _load_queue_snapshot(include_order=order_id)
    progress = find_progress_in_snapshot(snapshot, order_id)
    if not progress:
        progress = build_order_progress(order)
    return progress


@app.post("/orders/{order_id}/progress-chat", response_model=ProgressChatResponse)
async def progress_chat(order_id: int, payload: ProgressChatRequest):
    """基于制作进度的问答接口（兼容旧版）"""
    order = db.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    session_id = payload.session_id or f"progress-order-{order_id}"
    answer, mode, _, progress = await _answer_progress_question(
        session_id=session_id,
        user_text=payload.question,
        explicit_order_id=order_id,
    )
    return ProgressChatResponse(answer=answer, progress=progress, mode=mode, order_id=order_id)


@app.websocket("/ws/orders/{order_id}/status")
async def order_status_ws(websocket: WebSocket, order_id: int):
    """推送订单制作进度的 websocket"""
    await websocket.accept()
    try:
        while True:
            order = db.get_order(order_id)
            if not order:
                await websocket.send_json({"error": "订单不存在"})
                await asyncio.sleep(5)
                continue

            snapshot = _load_queue_snapshot(include_order=order_id)
            progress = find_progress_in_snapshot(snapshot, order_id)
            if not progress:
                progress = build_order_progress(order)
            await websocket.send_json(jsonable_encoder(progress))

            if progress.is_completed:
                break
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return


@app.get("/orders/{order_id}/progress-history", response_model=ProgressHistoryResponse)
async def get_progress_history(order_id: int):
    """获取制作进度助手历史"""
    order = db.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    history = session_manager.get_progress_history(order_id)
    return ProgressHistoryResponse(order_id=order_id, history=history)


@app.post("/progress/chat", response_model=ProgressChatResponse)
async def progress_chat_session(payload: ProgressSessionChatRequest):
    """会话级别的制作进度问答接口"""
    session_id = payload.session_id.strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id 不能为空")
    answer, mode, order_id, progress = await _answer_progress_question(
        session_id=session_id,
        user_text=payload.question,
        explicit_order_id=payload.order_id,
    )
    return ProgressChatResponse(answer=answer, progress=progress, mode=mode, order_id=order_id)


@app.get("/progress/history/{session_id}", response_model=ProgressSessionHistoryResponse)
async def get_progress_session_history(session_id: str):
    """获取会话级别的制作进度助手历史"""
    history = session_manager.get_progress_session_history(session_id)
    return ProgressSessionHistoryResponse(session_id=session_id, history=history)


@app.get("/production/queue")
async def get_production_queue(limit: int = 50):
    """获取制作排队面板"""
    snapshot = _load_queue_snapshot(limit=limit)
    return snapshot


@app.websocket("/ws/production/queue")
async def production_queue_ws(websocket: WebSocket):
    """推送全局排队信息"""
    await websocket.accept()
    try:
        while True:
            snapshot = _load_queue_snapshot()
            await websocket.send_json(jsonable_encoder(snapshot))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return


@app.post("/tts", response_model=TTSResponse)
async def text_to_speech(request: TTSRequest):
    """AssemblyAI 文本转语音"""
    if not config.ASSEMBLYAI_API_KEY:
        raise HTTPException(status_code=400, detail="ASSEMBLYAI_API_KEY 未配置")
    voice = request.voice or config.ASSEMBLYAI_TTS_VOICE or "alloy"
    payload = {"text": request.text, "voice": voice, "format": "mp3"}
    headers = {
        "authorization": config.ASSEMBLYAI_API_KEY,
        "content-type": "application/json",
    }
    url = f"{config.ASSEMBLYAI_API_URL}/text-to-speech/generate"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"TTS 失败: {response.text}")
        data = response.json()
        audio_url = data.get("audio_url")
        audio_base64 = data.get("audio_data") or data.get("audio_base64")
        if not audio_url and not audio_base64:
            audio_base64 = data.get("audio")
        return TTSResponse(
            audio_url=audio_url,
            audio_base64=audio_base64,
            voice=voice,
            format=data.get("format", "mp3"),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"TTS 请求失败: {exc}")


@app.websocket("/ws/stt")
async def realtime_stt_ws(websocket: WebSocket):
    """AssemblyAI 实时语音识别转发"""
    await websocket.accept()
    if not config.ASSEMBLYAI_API_KEY:
        await websocket.send_json({"error": "ASSEMBLYAI_API_KEY 未配置"})
        await websocket.close()
        return

    assembly_uri = "wss://api.assemblyai.com/v2/realtime/ws?sample_rate=16000"
    headers = {
        "Authorization": config.ASSEMBLYAI_API_KEY,
        "Accept": "application/json",
    }

    async def forward_client(to_ws):
        try:
            while True:
                message = await websocket.receive_text()
                payload = json.loads(message)
                if payload.get("event") == "flush":
                    await to_ws.send(json.dumps({"terminate_session": True}))
                    break
                audio_data = payload.get("audio_data")
                if audio_data:
                    await to_ws.send(json.dumps({"audio_data": audio_data}))
        except WebSocketDisconnect:
            pass

    async def forward_assembly(from_ws):
        try:
            async for msg in from_ws:
                await websocket.send_text(msg)
        except WebSocketDisconnect:
            pass

    try:
        async with websockets.connect(assembly_uri, extra_headers=headers) as assembly_ws:
            await asyncio.gather(
                forward_client(assembly_ws),
                forward_assembly(assembly_ws),
            )
    except WebSocketDisconnect:
        return
    except Exception as exc:
        await websocket.send_json({"error": str(exc)})


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
