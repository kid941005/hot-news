"""共享工具函数。

集中存放跨模块复用的轻量辅助逻辑，避免各 API 模块重复实现。
"""
from datetime import datetime, timezone


def as_utc(value) -> datetime:
    """将 naive/aware datetime 规范化为带时区的 UTC datetime。

    - naive datetime 视为 UTC（数据库统一存储 naive UTC）；
    - aware datetime 直接转 UTC。
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def as_utc_iso(value) -> str:
    """将 naive/aware datetime 规范化为带 Z 后缀的 UTC ISO 字符串。"""
    value = as_utc(value)
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")