"""FastAPI 后端主服务"""
import asyncio
from contextlib import asynccontextmanager
import json
from datetime import datetime
import math
import re
import aiohttp
import httpx
from fastapi import FastAPI, HTTPException, Form, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from typing import Optional

from .config import config
from .models import (
    SessionState,
    TalkResponse,
    OrderStatus,
    AgentAction,
    OrderProgressResponse,
    TTSRequest,
    TTSResponse,
    OrderMetadata,
    ProgressChatRequest,
    ProgressSessionRequest,
)
from .database import db
from .session_manager import session_manager
from .agent import tea_agent
from .production import build_order_progress, build_queue_snapshot, find_progress_in_snapshot
from .pricing import calculate_order_total
from .time_utils import parse_timestamp

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    print("🚀 Tea Order Agent System 启动成功！")
    print(f"📊 数据库路径: {config.DATABASE_PATH}")
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


def _load_queue_snapshot(limit: int = 50, include_order: Optional[int] = None):
    """加载队列快照"""
    orders = db.get_recent_orders(limit)
    if include_order and not any(order["id"] == include_order for order in orders):
        extra = db.get_order(include_order)
        if extra:
            orders.append(extra)
    return build_queue_snapshot(orders)


def _format_progress_answer(order_id: int, progress: OrderProgressResponse) -> str:
    """生成制作进度的自然语言描述"""
    stage = progress.current_stage_label
    if progress.eta_seconds:
        eta_minutes = max(1, math.ceil(progress.eta_seconds / 60))
        eta_text = f"预计 {eta_minutes} 分钟后完成"
    else:
        eta_text = "现在即可取餐"
    return f"订单 #{order_id} 当前处于{stage}阶段，{eta_text}。"


def _extract_order_id_from_text(text: str) -> Optional[int]:
    """从文本中提取订单号"""
    match = re.search(r"#?(\d+)", text or "")
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Tea Order Agent System API",
        "version": "1.0.0",
        "endpoints": {
            "WS /ws/stt": "实时语音识别 WebSocket",
            "POST /text": "处理文本输入",
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

    status = "healthy" if db_status == "ok" else "degraded"

    return {
        "status": status,
        "database": db_status
    }


@app.post("/text", response_model=TalkResponse)
async def text(session_id: str = Form(...), text: str = Form(...)):
    """
    处理文本输入（测试用，不需要语音）

    这个接口方便开发和测试，可以直接发送文本而不需要录音
    """
    return await _process_text(session_id, text)


async def _process_text(session_id: str, user_text: str) -> TalkResponse:
    """
    处理文本的核心逻辑

    Args:
        session_id: 会话 ID
        user_text: 用户输入的文本

    Returns:
        TalkResponse
    """
    session = session_manager.get_session(session_id)
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
    order_metadata: Optional[OrderMetadata] = None

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

        saved_order = db.get_order(order_id)
        placed_source = (
            saved_order.get("created_at_iso") or saved_order.get("created_at")
            if saved_order else None
        )
        if placed_source:
            placed_at = parse_timestamp(placed_source)
        else:
            placed_at = datetime.utcnow()
        order_metadata = OrderMetadata(order_id=order_id, session_id=session_id, placed_at=placed_at)

        # 在回复中添加订单号
        agent_response.assistant_reply += f" 订单号：#{order_id}"

        # 添加订单到历史记录，并自动清理超过 5 个订单的对话历史
        session_manager.add_order_to_history(session_id, order_id, max_orders=5)

        # 重置 order_state，避免后续被重复保存
        from .models import OrderState
        session_manager.update_order_state(session_id, OrderState())

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
        order_metadata=order_metadata,
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


@app.post("/orders/{order_id}/progress-chat")
async def order_progress_chat(order_id: int, payload: ProgressChatRequest):
    """针对指定订单的制作进度问答"""
    order = db.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    session_manager.add_progress_message(order_id, "user", payload.question)
    progress = build_order_progress(order)
    answer = _format_progress_answer(order_id, progress)
    session_manager.add_progress_message(order_id, "assistant", answer)
    return {
        "order_id": order_id,
        "progress": progress,
        "answer": answer,
    }


@app.get("/orders/{order_id}/progress-history")
async def get_order_progress_history(order_id: int):
    """获取指定订单的进度助手历史"""
    history = session_manager.get_progress_history(order_id)
    return {
        "order_id": order_id,
        "history": [message.model_dump() for message in history],
    }


@app.post("/progress/chat")
async def progress_chat(payload: ProgressSessionRequest):
    """面向生产助手的自然语言查询接口"""
    session_manager.add_progress_session_message(payload.session_id, "user", payload.question)
    order_id = _extract_order_id_from_text(payload.question)
    if not order_id:
        answer = "请提供有效的订单号（例如：订单 #123）。"
        session_manager.add_progress_session_message(payload.session_id, "assistant", answer, mode="offline")
        return {
            "session_id": payload.session_id,
            "order_id": None,
            "answer": answer,
        }

    order = db.get_order(order_id)
    if not order:
        answer = f"未找到订单 #{order_id}，请确认编号。"
        session_manager.add_progress_session_message(payload.session_id, "assistant", answer, mode="offline")
        return {
            "session_id": payload.session_id,
            "order_id": order_id,
            "answer": answer,
        }

    progress = build_order_progress(order)
    answer = _format_progress_answer(order_id, progress)
    session_manager.add_progress_session_message(payload.session_id, "assistant", answer)
    session_manager.add_progress_message(order_id, "user", payload.question)
    session_manager.add_progress_message(order_id, "assistant", answer)
    return {
        "session_id": payload.session_id,
        "order_id": order_id,
        "progress": progress,
        "answer": answer,
    }


@app.get("/progress/history/{session_id}")
async def get_progress_session_history(session_id: str):
    """查询会话级生产助手历史"""
    history = session_manager.get_progress_session_history(session_id)
    return {
        "session_id": session_id,
        "history": [message.model_dump() for message in history],
    }


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
    """AssemblyAI 实时语音识别转发，并在最终文本时触发会话逻辑"""
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
    session_id = websocket.query_params.get("session_id")

    async def forward_client(to_ws: aiohttp.ClientWebSocketResponse):
        try:
            while True:
                message = await websocket.receive_text()
                payload = json.loads(message)
                if payload.get("event") == "flush":
                    await to_ws.send_json({"terminate_session": True})
                    await to_ws.close()
                    break
                audio_data = payload.get("audio_data")
                if audio_data:
                    await to_ws.send_json({"audio_data": audio_data})
        except WebSocketDisconnect:
            await to_ws.close()

    async def dispatch_agent_response(text: str):
        if not session_id or not text.strip():
            return

        async def safe_process():
            try:
                response = await _process_text(session_id, text)
                await websocket.send_json({
                    "message_type": "agent_response",
                    "payload": jsonable_encoder(response),
                })
            except HTTPException as exc:
                await websocket.send_json({
                    "message_type": "agent_response_error",
                    "detail": exc.detail,
                })
            except Exception as exc:
                await websocket.send_json({
                    "message_type": "agent_response_error",
                    "detail": str(exc),
                })

        asyncio.create_task(safe_process())

    async def forward_assembly(from_ws: aiohttp.ClientWebSocketResponse):
        try:
            async for msg in from_ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await websocket.send_text(msg.data)
                    if not session_id:
                        continue
                    try:
                        data = json.loads(msg.data)
                    except json.JSONDecodeError:
                        continue
                    if data.get("message_type") == "final_transcript" and data.get("text"):
                        await dispatch_agent_response(data["text"])
                elif msg.type == aiohttp.WSMsgType.BINARY:
                    await websocket.send_bytes(msg.data)
                elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED):
                    break
        except WebSocketDisconnect:
            pass

    aiohttp_session = aiohttp.ClientSession()
    try:
        async with aiohttp_session.ws_connect(assembly_uri, headers=headers, heartbeat=15) as assembly_ws:
            await asyncio.gather(
                forward_client(assembly_ws),
                forward_assembly(assembly_ws),
            )
    except asyncio.CancelledError:
        raise
    except aiohttp.ClientError as exc:
        await websocket.send_json({"error": f"连接 AssemblyAI 失败: {exc}"})
    except Exception as exc:
        await websocket.send_json({"error": str(exc)})
    finally:
        await aiohttp_session.close()


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
