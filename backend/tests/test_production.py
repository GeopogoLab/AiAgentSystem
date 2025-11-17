"""制作进度计算测试"""
from datetime import datetime, timedelta
from backend.production import build_order_progress, STAGE_DEFINITIONS


def test_progress_before_completion():
    order = {
        "id": 99,
        "created_at": (datetime.utcnow() - timedelta(seconds=60)).strftime("%Y-%m-%d %H:%M:%S")
    }
    now = datetime.utcnow()
    progress = build_order_progress(order, reference_time=now)

    assert progress.order_id == 99
    assert progress.current_stage_label == STAGE_DEFINITIONS[1]["label"]
    assert progress.is_completed is False
    assert progress.eta_seconds is not None
    assert len(progress.timeline) == len(STAGE_DEFINITIONS)


def test_progress_after_completion():
    order = {
        "id": 100,
        "created_at": (datetime.utcnow() - timedelta(seconds=600)).strftime("%Y-%m-%d %H:%M:%S")
    }
    now = datetime.utcnow()
    progress = build_order_progress(order, reference_time=now)

    assert progress.is_completed is True
    assert progress.current_stage_label == STAGE_DEFINITIONS[-1]["label"]
    assert progress.eta_seconds is None
    ready_stage = progress.timeline[-1]
    assert ready_stage.stage.value == "ready"
