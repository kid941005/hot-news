#!/usr/bin/env python3
"""
配置模块：平台列表、用户标签与关键词配置接口。
"""
import json
import logging
from datetime import timezone
from typing import List, Optional

from apscheduler.triggers.cron import CronTrigger
from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from backend.api.auth import get_current_user_id
from backend.api.push_service import ALLOWED_PUSH_CHANNELS
from backend.utils import as_utc_iso
from backend.db import database
from backend.db.database import PLATFORM_MAP, REALTIME_PLATFORM_IDS
from backend.models.models import get_db

logger = logging.getLogger(__name__)

config_router = APIRouter()

UTC = timezone.utc

MAX_KEYWORDS = 100
MAX_KEYWORD_LENGTH = 50
MAX_TAGS = 30
MAX_TAG_LENGTH = 30
MAX_WEBHOOK_LENGTH = 500


def _clean_string_list(values, field_name, max_items=MAX_KEYWORDS, max_length=MAX_KEYWORD_LENGTH):
    if values is None:
        return values
    if len(values) > max_items:
        raise ValueError(f"{field_name} 最多支持 {max_items} 项")
    cleaned = []
    for value in values:
        if not isinstance(value, str):
            raise ValueError(f"{field_name} 必须是字符串列表")
        item = value.strip()
        if not item:
            continue
        if len(item) > max_length:
            raise ValueError(f"{field_name} 单项最多 {max_length} 个字符")
        cleaned.append(item)
    return cleaned


class ConfigRequest(BaseModel):
    keywords: Optional[List[str]] = None
    blocked_keywords: Optional[List[str]] = None
    keyword_tags: Optional[dict] = None  # 关键词标签映射
    platforms: Optional[List[str]] = None
    push_enabled: Optional[bool] = None
    push_channel: Optional[str] = None
    push_webhook: Optional[str] = None
    push_cron: Optional[str] = None  # cron 表达式，如 "0 */4 * * *"

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, values):
        return _clean_string_list(values, "keywords")

    @field_validator("blocked_keywords")
    @classmethod
    def validate_blocked_keywords(cls, values):
        return _clean_string_list(values, "blocked_keywords")

    @field_validator("platforms")
    @classmethod
    def validate_platforms(cls, values):
        values = _clean_string_list(values, "platforms", max_items=len(PLATFORM_MAP), max_length=30)
        if values is None:
            return values
        unknown = [value for value in values if value not in PLATFORM_MAP]
        if unknown:
            raise ValueError(f"不支持的平台: {', '.join(unknown)}")
        return values

    @field_validator("keyword_tags")
    @classmethod
    def validate_keyword_tags(cls, values):
        if values is None:
            return values
        if not isinstance(values, dict):
            raise ValueError("keyword_tags 必须是对象")
        if len(values) > MAX_TAGS:
            raise ValueError(f"标签最多支持 {MAX_TAGS} 个")
        cleaned = {}
        total_keywords = 0
        for tag, keywords in values.items():
            if not isinstance(tag, str):
                raise ValueError("标签名必须是字符串")
            tag_name = tag.strip()
            if not tag_name:
                continue
            if len(tag_name) > MAX_TAG_LENGTH:
                raise ValueError(f"标签名最多 {MAX_TAG_LENGTH} 个字符")
            tag_keywords = _clean_string_list(keywords or [], "keyword_tags", max_items=MAX_KEYWORDS)
            total_keywords += len(tag_keywords)
            if total_keywords > MAX_KEYWORDS:
                raise ValueError(f"标签关键词总数最多支持 {MAX_KEYWORDS} 项")
            cleaned[tag_name] = tag_keywords
        return cleaned

    @field_validator("push_channel")
    @classmethod
    def validate_push_channel(cls, value):
        if value is None:
            return value
        if value not in ALLOWED_PUSH_CHANNELS:
            raise ValueError("不支持的推送渠道")
        return value

    @field_validator("push_webhook")
    @classmethod
    def validate_push_webhook(cls, value):
        if value is None:
            return value
        value = value.strip()
        if len(value) > MAX_WEBHOOK_LENGTH:
            raise ValueError(f"Webhook 最多 {MAX_WEBHOOK_LENGTH} 个字符")
        return value

    @field_validator("push_cron")
    @classmethod
    def validate_push_cron(cls, value):
        if value is None:
            return value
        value = value.strip()
        if len(value) > 100:
            raise ValueError("cron 表达式过长")
        try:
            CronTrigger.from_crontab(value, timezone=UTC)
        except ValueError as exc:
            raise ValueError("cron 表达式无效") from exc
        return value



@config_router.get("/api/platforms")
def get_platforms():
    return {
        "success": True,
        "platforms": [
            {"id": k, "name": v, "realtime": k in REALTIME_PLATFORM_IDS}
            for k, v in PLATFORM_MAP.items()
        ]
    }


@config_router.get("/api/config")
def get_config(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    config = database.get_user_config(db, user_id)
    if not config:
        return {"success": True, "config": {}}
    return {
        "success": True,
        "config": {
            "keywords": config.keywords or [],
            "blocked_keywords": config.blocked_keywords or [],
            "keyword_tags": config.keyword_tags or {},
            "platforms": config.platforms or [],
            "push_enabled": config.push_enabled or False,
            "push_channel": config.push_channel or "feishu",
            "push_webhook": config.push_webhook or "",
            "push_cron": config.push_cron or "0 */4 * * *",
            "last_push_at": as_utc_iso(config.last_push_at),
        }
    }


@config_router.get("/api/tags")
def get_tags(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """获取用户的标签列表"""
    config = database.get_user_config(db, user_id)
    if not config or config.keyword_tags is None:
        # 返回默认标签（仅当没有任何配置时）
        return {
            "success": True,
            "tags": ["工作", "生活", "科技"],
            "keyword_tags": {}
        }

    keyword_tags = config.keyword_tags
    if isinstance(keyword_tags, str):
        keyword_tags = json.loads(keyword_tags)

    # 提取所有标签（用户删除的标签不再显示）
    all_tags = list(keyword_tags.keys())

    # 按默认顺序排序（工作、生活、科技、其他）
    default_order = ["工作", "生活", "科技"]
    sorted_tags = []
    for tag in default_order:
        if tag in all_tags:
            sorted_tags.append(tag)
    for tag in all_tags:
        if tag not in default_order:
            sorted_tags.append(tag)

    return {
        "success": True,
        "tags": sorted_tags,
        "keyword_tags": keyword_tags
    }


@config_router.post("/api/config")
def update_config(req: ConfigRequest, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    config_data = req.dict(exclude_unset=True)
    database.update_user_config(db, user_id, config_data)
    return {"success": True}
