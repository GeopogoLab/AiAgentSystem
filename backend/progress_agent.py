"""制作进度智能播报 Agent"""
import json
import logging
from typing import Optional, Tuple, List
from openai import AsyncOpenAI
from fastapi.encoders import jsonable_encoder

from .config import config
from .models import OrderProgressResponse, ProductionQueueSnapshot

logger = logging.getLogger(__name__)


class ProgressAgent:
    """用于播报制作进度的 Agent"""

    def __init__(self):
        api_key = (config.OPENROUTER_API_KEY or "").strip()
        if api_key:
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=config.OPENROUTER_BASE_URL,
                default_headers=self._headers(),
            )
        else:
            logger.warning("未配置 OPENROUTER_API_KEY，制作进度助手将使用离线播报。")
            self.client = None
        self.model = config.OPENROUTER_MODEL

    def _headers(self):
        headers = {}
        if config.OPENROUTER_SITE_URL:
            headers["HTTP-Referer"] = config.OPENROUTER_SITE_URL
        if config.OPENROUTER_SITE_NAME:
            headers["X-Title"] = config.OPENROUTER_SITE_NAME
        return headers

    async def answer(
        self,
        question: str,
        progress: Optional[OrderProgressResponse],
        snapshot: Optional[ProductionQueueSnapshot],
    ) -> Tuple[str, str]:
        summary = self._build_progress_summary(progress, snapshot)
        if not self.client:
            return summary, "offline"

        try:
            context = {
                "question": question,
                "has_progress": progress is not None,
                "progress": jsonable_encoder(progress) if progress else None,
                "queue_snapshot": jsonable_encoder(snapshot) if snapshot else None,
            }
            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是奶茶店的制作进度播报员。"
                        "必须依据提供的结构化数据回答，不可臆测。"
                        "queue_snapshot 给出了所有排队中与刚完成的订单列表，可用于回答“现场还有几单”“最近完成的是谁”等问题。"
                        "如果提供了 progress，就说明顾客给出了订单号，请根据 progress 和 queue_snapshot 里的数据回答当前阶段、排队位置、剩余时间。"
                        "如果没有提供 progress（用户未提供订单号），请先利用 queue_snapshot 总结整体排队情况，再礼貌地询问订单号以及任何你需要的唯一标识，不要臆测状态。"
                        "回答保持中文、简洁友好。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(context, ensure_ascii=False),
                },
            ]

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
            )
            return response.choices[0].message.content, "online"
        except Exception as exc:
            logger.warning("进度助手 LLM 调用失败，切换离线模式：%s", exc)
            return summary, "offline"

    def _build_progress_summary(
        self,
        progress: Optional[OrderProgressResponse],
        snapshot: Optional[ProductionQueueSnapshot],
    ) -> str:
        if not progress:
            if snapshot and snapshot.active_orders:
                waiting = len(snapshot.active_orders)
                queue_ids = "、".join(f"#{item.order_id}" for item in snapshot.active_orders[:5])
                base = f"目前共有 {waiting} 单在制作中：{queue_ids}。"
                return base + "请告诉我您的订单号或取餐编号，我才能播报具体进度。"
            if snapshot and snapshot.completed_orders:
                recent = "、".join(f"#{item.order_id}" for item in snapshot.completed_orders[:3])
                return f"最近完成的订单有：{recent}。请告诉我您的订单号（或取餐编号），我才能查询进度。"
            return "请告诉我订单号（或取餐编号），我才能查询进度。"
        if progress.is_completed:
            return f"订单 #{progress.order_id} 已完成，可以随时取餐。"

        details: List[str] = []
        if progress.queue_position and progress.total_orders:
            details.append(f"当前排在第 {progress.queue_position}/{progress.total_orders} 位")
        if progress.eta_seconds:
            minutes = max(1, int(progress.eta_seconds // 60))
            details.append(f"预计约 {minutes} 分钟后完成")
        eta = ("，".join(details) + "。") if details else ""

        next_steps = [item.label for item in progress.timeline if not item.finished_at]
        next_text = f" 后续流程：{' → '.join(next_steps)}。" if next_steps else ""

        return (
            f"订单 #{progress.order_id} 正在进行「{progress.current_stage_label}」阶段。"
            f"{eta}{next_text}".strip()
        )


progress_agent = ProgressAgent()
