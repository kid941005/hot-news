#!/usr/bin/env python3
"""统一的环境变量解析工具。"""
import logging
import os
from typing import Optional


logger = logging.getLogger(__name__)


def get_env_int(
    name: str,
    default: int,
    min_value: int = 1,
    max_value: Optional[int] = None,
) -> int:
    """读取整数环境变量；非法或越界时回退到默认值。"""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("%s=%r 无效，使用默认值 %s", name, raw, default)
        return default
    if value < min_value or (max_value is not None and value > max_value):
        logger.warning("%s=%r 超出范围，使用默认值 %s", name, raw, default)
        return default
    return value


def get_env_float(
    name: str,
    default: float,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
) -> float:
    """读取浮点环境变量；非法或越界时回退到默认值。"""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning("%s=%r 无效，使用默认值 %s", name, raw, default)
        return default
    if (min_value is not None and value < min_value) or (max_value is not None and value > max_value):
        logger.warning("%s=%r 超出范围，使用默认值 %s", name, raw, default)
        return default
    return value
