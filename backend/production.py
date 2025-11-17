"""订单制作进度计算"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Optional, List

from .models import (
    OrderProgressResponse,
    ProductionTimelineItem,
    ProductionStage,
    ProductionQueueSnapshot,
)

STAGE_DEFINITIONS = [
    {"stage": ProductionStage.QUEUED, "label": "排队中", "duration": 30},
    {"stage": ProductionStage.BREWING, "label": "制作中", "duration": 120},
    {"stage": ProductionStage.SEALING, "label": "封杯打包", "duration": 45},
    {"stage": ProductionStage.READY, "label": "可取餐", "duration": 0},
]


def _parse_datetime(value: str) -> datetime:
    """解析 SQLite 时间戳"""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"无法解析时间戳: {value}")


def build_order_progress(order: Dict, reference_time: Optional[datetime] = None) -> OrderProgressResponse:
    """根据订单创建时间计算制作进度"""
    created_at = order.get("created_at")
    if not created_at:
        raise ValueError("订单缺少 created_at 字段")

    order_created_at = created_at if isinstance(created_at, datetime) else _parse_datetime(created_at)
    now = reference_time or datetime.utcnow()
    elapsed = max(0, (now - order_created_at).total_seconds())

    total_duration = sum(stage["duration"] for stage in STAGE_DEFINITIONS if stage["duration"] > 0)
    is_completed = elapsed >= total_duration
    remaining_seconds = 0 if is_completed else int(total_duration - elapsed)

    timeline_items: List[ProductionTimelineItem] = []
    cumulative = 0
    current_stage = ProductionStage.READY if is_completed else ProductionStage.QUEUED
    current_label = STAGE_DEFINITIONS[-1]["label"] if is_completed else STAGE_DEFINITIONS[0]["label"]

    for stage_def in STAGE_DEFINITIONS:
        duration = stage_def["duration"]
        stage_start = order_created_at + timedelta(seconds=cumulative)
        finished_at: Optional[datetime] = None

        if duration == 0:
            if is_completed:
                finished_at = now
            timeline_items.append(
                ProductionTimelineItem(
                    stage=stage_def["stage"],
                    label=stage_def["label"],
                    started_at=stage_start,
                    finished_at=finished_at,
                    duration_seconds=None,
                )
            )
            break

        stage_end = stage_start + timedelta(seconds=duration)

        if elapsed >= cumulative + duration:
            finished_at = stage_end
        elif not is_completed and elapsed >= cumulative:
            current_stage = stage_def["stage"]
            current_label = stage_def["label"]

        timeline_items.append(
            ProductionTimelineItem(
                stage=stage_def["stage"],
                label=stage_def["label"],
                started_at=stage_start,
                finished_at=finished_at,
                duration_seconds=duration,
            )
        )

        cumulative += duration

    return OrderProgressResponse(
        order_id=order["id"],
        current_stage=current_stage,
        current_stage_label=current_label,
        eta_seconds=remaining_seconds if not is_completed else None,
        total_duration_seconds=total_duration,
        is_completed=is_completed,
        timeline=timeline_items,
    )


def build_queue_snapshot(orders: List[Dict], reference_time: Optional[datetime] = None) -> ProductionQueueSnapshot:
    """构建排队面板快照"""
    now = reference_time or datetime.utcnow()
    if not orders:
        return ProductionQueueSnapshot(
            generated_at=now,
            active_orders=[],
            completed_orders=[],
        )

    sorted_orders = sorted(
        orders,
        key=lambda order: _parse_datetime(order["created_at"]) if isinstance(order.get("created_at"), str) else order.get("created_at", now)
    )
    progress_map: Dict[int, OrderProgressResponse] = {}
    for order in sorted_orders:
        progress_map[order["id"]] = build_order_progress(order, reference_time=now)

    active = []
    completed = []
    for order in sorted_orders:
        progress = progress_map[order["id"]]
        if progress.is_completed:
            completed.append(progress)
        else:
            active.append(progress)

    total_active = len(active)
    for idx, progress in enumerate(active, start=1):
        progress.queue_position = idx
        progress.total_orders = total_active

    for progress in completed:
        progress.queue_position = None
        progress.total_orders = total_active

    completed = sorted(
        completed,
        key=lambda p: next((item.finished_at for item in reversed(p.timeline) if item.finished_at), now),
        reverse=True
    )[:10]

    return ProductionQueueSnapshot(
        generated_at=now,
        active_orders=active,
        completed_orders=completed,
    )


def find_progress_in_snapshot(snapshot: ProductionQueueSnapshot, order_id: int) -> Optional[OrderProgressResponse]:
    for progress in snapshot.active_orders:
        if progress.order_id == order_id:
            return progress
    for progress in snapshot.completed_orders:
        if progress.order_id == order_id:
            return progress
    return None
