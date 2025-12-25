"""FastAPI backend main service"""
import asyncio
import base64
import binascii
from contextlib import asynccontextmanager
import io
import json
import logging
from datetime import datetime
import math
import re
from typing import Optional
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

import aiohttp
import httpx
from fastapi import FastAPI, HTTPException, Form, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
# gTTS is optional dependency, for demo mode
try:
    from gtts import gTTS  # type: ignore
except ImportError:  # pragma: no cover
    gTTS = None
from starlette.websockets import WebSocketState

from .config import config
from .models import (
    SessionState,
    TalkResponse,
    OrderStatus,
    AgentAction,
    OrderProgressResponse,
    TTSRequest,
    TTSResponse,
    OrderState,
    OrderMetadata,
    ProgressChatRequest,
    ProgressSessionRequest,
)
from .database import db
from .session_manager import session_manager
from .agent import tea_agent
from .local_tts import synthesize_local_tts
from .production import build_order_progress, build_queue_snapshot, find_progress_in_snapshot
from .pricing import calculate_order_total
from .time_utils import parse_timestamp
from .stt.backends import STTBackendRouter

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle"""
    print("🚀 Tea Order Agent System started successfully!")
    print(f"📊 Database path: {config.DATABASE_PATH}")
    yield


# Create FastAPI application
app = FastAPI(
    title="Tea Order Agent System",
    description="Tea Order AI Agent System",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production should limit to specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize STT router (manages AssemblyAI / Whisper fallback)
stt_router = STTBackendRouter(config)


def _load_queue_snapshot(limit: int = 50, include_order: Optional[int] = None):
    """Load queue snapshot"""
    orders = db.get_recent_orders(limit)
    if include_order and not any(order["id"] == include_order for order in orders):
        extra = db.get_order(include_order)
        if extra:
            orders.append(extra)
    return build_queue_snapshot(orders)


def _build_order_metadata_snapshot(session_id: str, order_id: int) -> OrderMetadata:
    saved_order = db.get_order(order_id)
    placed_source = (
        saved_order.get("created_at_iso") or saved_order.get("created_at")
        if saved_order else None
    )
    if placed_source:
        placed_at = parse_timestamp(placed_source)
    else:
        placed_at = datetime.utcnow()
    return OrderMetadata(order_id=order_id, session_id=session_id, placed_at=placed_at)


async def _synthesize_with_gtts(text: str, voice: Optional[str] = None) -> TTSResponse:
    """Generate speech using gTTS"""
    if gTTS is None:
        raise HTTPException(status_code=500, detail="gTTS not installed, please run pip install gTTS")
    lang = config.GTTS_LANGUAGE
    if voice:
        # Allow voice to override lang, e.g., "en" / "zh-CN"
        lang = voice

    loop = asyncio.get_running_loop()

    def _render() -> str:
        tts = gTTS(text=text, lang=lang, slow=config.GTTS_SLOW)
        buffer = io.BytesIO()
        tts.write_to_fp(buffer)
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode("utf-8")

    audio_base64 = await loop.run_in_executor(None, _render)
    return TTSResponse(
        audio_base64=audio_base64,
        voice=lang,
        format="mp3",
    )


def _order_state_signature(order_state: OrderState) -> tuple:
    """Extract core field signature from order state for duplicate detection"""
    def normalize(value: Optional[str]) -> str:
        if value is None:
            return ""
        return str(value).strip()

    toppings = sorted(normalize(item) for item in (order_state.toppings or []))
    return (
        normalize(order_state.drink_name),
        normalize(order_state.size),
        normalize(order_state.sugar),
        normalize(order_state.ice),
        tuple(toppings),
        normalize(order_state.notes),
    )


def _format_progress_answer(order_id: int, progress: OrderProgressResponse) -> str:
    """Generate natural language description of production progress"""
    stage = progress.current_stage_label
    if progress.eta_seconds:
        eta_minutes = max(1, math.ceil(progress.eta_seconds / 60))
        eta_text = f"estimated {eta_minutes} minute(s) to completion"
    else:
        eta_text = "ready for pickup now"
    return f"Order #{order_id} is currently in {stage} stage, {eta_text}."


def _extract_order_id_from_text(text: str) -> Optional[int]:
    """Extract order number from text"""
    match = re.search(r"#?(\d+)", text or "")
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


@app.get("/")
async def root():
    """Root path"""
    return {
        "message": "Tea Order Agent System API",
        "version": "1.0.0",
        "endpoints": {
            "WS /ws/stt": "Real-time speech recognition WebSocket",
            "POST /text": "Process text input",
            "GET /orders/{order_id}": "Query order",
            "GET /orders": "Query all orders",
            "GET /session/{session_id}": "Query session state",
            "POST /reset/{session_id}": "Reset session"
        }
    }


@app.get("/health")
async def health():
    """Health check"""
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
    Process text input (for testing, no voice needed)

    This endpoint is convenient for development and testing, allowing direct text submission without recording
    """
    return await _process_text(session_id, text)


async def _process_text(session_id: str, user_text: str) -> TalkResponse:
    """
    Core logic for processing text

    Args:
        session_id: Session ID
        user_text: User input text

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
        existing_snapshot = current_session.last_saved_order_state
        existing_signature = _order_state_signature(existing_snapshot) if existing_snapshot else None
        incoming_signature = _order_state_signature(agent_response.order_state)
        is_duplicate = (
            current_session.status == OrderStatus.SAVED
            and current_session.last_order_id is not None
            and existing_snapshot is not None
            and existing_signature == incoming_signature
        )

        if is_duplicate:
            order_id = current_session.last_order_id
            order_total = current_session.last_order_total
            order_metadata = current_session.last_order_metadata
            if not order_metadata and order_id is not None:
                order_metadata = _build_order_metadata_snapshot(session_id, order_id)
                current_session.last_order_metadata = order_metadata

            agent_response.assistant_reply = (
                f"订单 #{order_id} 已保存，无需重复提交。如需新的订单请告诉我新的饮品需求。"
            )
            agent_response.order_state = existing_snapshot.model_copy(deep=True)
            session_manager.update_status(session_id, OrderStatus.SAVED)
            session_manager.update_order_state(session_id, OrderState())
        else:
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

            order_metadata = _build_order_metadata_snapshot(session_id, order_id)
            current_session.last_saved_order_state = agent_response.order_state.model_copy(deep=True)
            current_session.last_order_metadata = order_metadata

            # 在回复中添加订单号
            agent_response.assistant_reply += f" 订单号：#{order_id}"

            # 添加订单到历史记录，并自动清理超过 5 个订单的对话历史
            session_manager.add_order_to_history(session_id, order_id, max_orders=5)

            # 重置 order_state，避免后续被重复保存
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
    """文本转语音（AssemblyAI 或 gTTS）"""
    text = (request.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="缺少文本内容")

    provider = (config.TTS_PROVIDER or "assemblyai").lower()
    if provider == "local":
        return await synthesize_local_tts(text, request.voice)
    if provider == "gtts":
        try:
            return await _synthesize_with_gtts(text, request.voice)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"gTTS 请求失败: {exc}")

    if provider != "assemblyai":
        provider = "assemblyai"

    if not config.ASSEMBLYAI_API_KEY:
        try:
            return await _synthesize_with_gtts(text, request.voice)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"gTTS 请求失败: {exc}")

    voice = request.voice or config.ASSEMBLYAI_TTS_VOICE or "alloy"
    payload = {"text": text, "voice": voice, "format": "mp3"}
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
    """实时语音识别 WebSocket（透明降级：AssemblyAI → Whisper）"""
    await websocket.accept()

    # 获取 primary/fallback（统一接口）
    primary = stt_router.primary
    fallback = stt_router.fallback

    if not primary:
        await websocket.send_json({"error": "未配置 STT 服务（需要 ASSEMBLYAI_API_KEY 或 WHISPER_SERVICE_URL）"})
        await websocket.close()
        return

    session_id = websocket.query_params.get("session_id")

    # 尝试连接后端（primary → fallback）
    for backend in [primary, fallback]:
        if backend is None:
            continue

        try:
            logger.info(f"尝试连接 {backend.name} STT 服务...")

            # 统一超时检测（覆盖连接+运行时）
            async with asyncio.timeout(backend.timeout):
                await _connect_stt_backend(websocket, backend, session_id)
                return  # 成功，结束

        except (asyncio.TimeoutError, aiohttp.ClientError, Exception) as exc:
            # 所有错误统一处理
            logger.warning(f"⚠️ {backend.name} 失败: {type(exc).__name__}: {exc}")

            # 如果不是最后一个后端，尝试降级
            if backend == primary and fallback:
                await websocket.send_json({
                    "message_type": "fallback_notice",
                    "from": backend.name,
                    "to": fallback.name,
                    "reason": f"{type(exc).__name__}"
                })
                continue  # 尝试 fallback
            else:
                # 最后一个后端也失败了
                await websocket.send_json({"error": f"所有 STT 后端失败: {exc}"})
                await websocket.close()
                return


async def _connect_stt_backend(websocket: WebSocket, backend, session_id: Optional[str]):
    """透明代理：连接 STT 后端并双向转发（AssemblyAI/Whisper 通用）"""

    # 构建 WebSocket URL（AssemblyAI 需要查询参数）
    ws_url = backend.websocket_url
    if backend.name == "assemblyai":
        params = {
            "sample_rate": config.ASSEMBLYAI_STREAMING_SAMPLE_RATE,
            "encoding": config.ASSEMBLYAI_STREAMING_ENCODING,
            "speech_model": config.ASSEMBLYAI_STREAMING_MODEL,
        }
        ws_url = f"{ws_url}?{urlencode(params)}"

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(ws_url, headers=backend.headers, heartbeat=15) as remote_ws:
            logger.info(f"✅ 成功连接到 {backend.name}")

            # 辅助函数：安全发送给客户端
            async def send_client(payload: dict):
                if websocket.client_state != WebSocketState.CONNECTED:
                    return
                try:
                    await websocket.send_json(payload)
                except (WebSocketDisconnect, RuntimeError):
                    pass

            # 辅助函数：触发 Agent 响应
            async def dispatch_agent_response(text: str):
                if not session_id or not text.strip():
                    return

                async def safe_process():
                    try:
                        response = await _process_text(session_id, text)
                        await send_client({
                            "message_type": "agent_response",
                            "payload": jsonable_encoder(response),
                        })
                    except HTTPException as exc:
                        await send_client({
                            "message_type": "agent_response_error",
                            "detail": exc.detail,
                        })
                    except Exception as exc:
                        await send_client({
                            "message_type": "agent_response_error",
                            "detail": str(exc),
                        })

                asyncio.create_task(safe_process())

            # 双向转发
            async def forward_client_to_remote():
                """前端 → 后端"""
                try:
                    while True:
                        message = await websocket.receive_text()
                        data = json.loads(message)

                        if data.get("event") == "flush":
                            await remote_ws.close()
                            break

                        audio_data = data.get("audio_data")
                        if audio_data:
                            try:
                                audio_bytes = base64.b64decode(audio_data)
                                if audio_bytes:
                                    # AssemblyAI 需要二进制，Whisper 需要 JSON
                                    if backend.name == "assemblyai":
                                        await remote_ws.send_bytes(audio_bytes)
                                    else:  # whisper
                                        await remote_ws.send_str(json.dumps({"audio_data": audio_data}))
                            except (ValueError, binascii.Error):
                                continue
                except WebSocketDisconnect:
                    await remote_ws.close()

            async def forward_remote_to_client():
                """后端 → 前端（处理不同协议）"""
                processed_turns: set[int] = set()  # AssemblyAI 去重

                try:
                    async for msg in remote_ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                            except json.JSONDecodeError:
                                await send_client({"message_type": "stt_raw", "payload": msg.data})
                                continue

                            # AssemblyAI 协议处理
                            if backend.name == "assemblyai":
                                data_type = data.get("type")
                                if data_type == "Begin":
                                    await send_client({
                                        "message_type": "assembly_session",
                                        "session_id": data.get("id"),
                                        "expires_at": data.get("expires_at"),
                                    })
                                    continue
                                if data_type == "Termination":
                                    await send_client({
                                        "message_type": "assembly_termination",
                                        "reason": data.get("reason"),
                                    })
                                    continue
                                if data_type != "Turn":
                                    await send_client({"message_type": "assembly_raw", "payload": data})
                                    continue

                                # Turn 事件处理
                                transcript = data.get("transcript") or ""
                                if transcript:
                                    await send_client({"message_type": "partial_transcript", "text": transcript})

                                turn_order = data.get("turn_order")
                                final_text = (data.get("utterance") or transcript or "").strip()
                                if (
                                    data.get("end_of_turn")
                                    and final_text
                                    and turn_order is not None
                                    and turn_order not in processed_turns
                                ):
                                    processed_turns.add(turn_order)
                                    await send_client({"message_type": "final_transcript", "text": final_text})
                                    await dispatch_agent_response(final_text)

                            # Whisper 协议处理（简单）
                            else:
                                # 透传所有消息
                                await send_client(data)

                                # 检测 final_transcript，触发 Agent
                                if data.get("message_type") == "final_transcript":
                                    text = data.get("text", "").strip()
                                    if text:
                                        logger.info(f"收到最终识别: {text}")
                                        await dispatch_agent_response(text)

                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            await websocket.send_bytes(msg.data)
                        elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSE):
                            break
                except WebSocketDisconnect:
                    pass

            # 并发双向转发
            await asyncio.gather(
                forward_client_to_remote(),
                forward_remote_to_client()
            )


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
