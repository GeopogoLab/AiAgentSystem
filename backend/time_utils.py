"""时间处理工具"""
from __future__ import annotations

from datetime import datetime
from typing import Union

_SQLITE_TIMESTAMP_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
)


def parse_timestamp(value: Union[str, datetime]) -> datetime:
    """将 SQLite/ISO 格式的时间戳解析为 datetime."""
    if isinstance(value, datetime):
        return value
    if value is None:
        raise ValueError("缺少时间戳字段")

    text = str(value).strip()
    # 优先尝试 ISO 8601
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass

    for fmt in _SQLITE_TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    raise ValueError(f"无法解析时间戳: {value}")
