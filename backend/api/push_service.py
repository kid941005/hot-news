#!/usr/bin/env python3
"""推送模块：飞书/钉钉/Bark 推送、Webhook 校验与定时推送调度。"""
import ipaddress
import logging
import os
import re
import socket
from datetime import datetime, timezone
from typing import Dict
from urllib.parse import urlparse

from apscheduler.triggers.cron import CronTrigger
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.auth import get_current_user_id
from backend.db import database
from backend.models.models import SessionLocal, UserConfig, get_db

logger = logging.getLogger(__name__)

push_router = APIRouter()

UTC = timezone.utc


def _is_public_hostname(hostname: str) -> bool:
    if not hostname:
        return False
    lowered = hostname.lower()
    if lowered in {"localhost", "0.0.0.0"} or lowered.endswith(".local"):
        return False
    try:
        addresses = socket.getaddrinfo(lowered, None)
    except socket.gaierror:
        return False
    for item in addresses:
        ip = ipaddress.ip_address(item[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return False
    return True


def is_allowed_webhook(channel: str, webhook: str) -> bool:
    parsed = urlparse(webhook or "")
    if parsed.scheme != "https" or not _is_public_hostname(parsed.hostname or ""):
        return False
    host = (parsed.hostname or "").lower()
    if channel == "feishu":
        return host == "open.feishu.cn" and parsed.path.startswith("/open-apis/bot/v2/hook/")
    if channel == "dingtalk":
        return host == "oapi.dingtalk.com" and parsed.path == "/robot/send"
    if channel == "bark":
        allowed = {h.strip().lower() for h in os.getenv("BARK_WEBHOOK_HOSTS", "api.day.app").split(",") if h.strip()}
        return host in allowed
    return False


def push_to_feishu(webhook: str, content: str) -> bool:
    """推送消息到飞书（使用 post 富文本保留 Markdown 效果）"""
    import requests

    # 飞书机器人 webhook 不能可靠渲染通用 markdown 消息体，
    # 这里将现有内容按行转换为 post 富文本，保留标题、分组和链接。
    try:
        lines = [line.strip() for line in content.splitlines()]
        title = "热点资讯"
        body_lines = []
        link_pattern = re.compile(r"^(\d+)\. \[(.*?)\] \[(.*?)\]\((https?://[^)]+)\)$")

        for line in lines:
            if not line:
                continue
            if line.startswith("📰 "):
                title = line
                continue
            if line.startswith("### "):
                body_lines.append([{"tag": "text", "text": line[4:]}])
                continue

            match = link_pattern.match(line)
            if match:
                index, platform, text, url = match.groups()
                body_lines.append([
                    {"tag": "text", "text": f"{index}. [{platform}] "},
                    {"tag": "a", "text": text, "href": url},
                ])
                continue

            body_lines.append([{"tag": "text", "text": line}])

        payload = {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": title,
                        "content": body_lines,
                    }
                }
            }
        }

        response = requests.post(webhook, json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json()
            return result.get("code", 0) == 0
        return False
    except Exception:
        logger.exception("飞书推送失败")
        return False


def push_to_dingtalk(webhook: str, content: str) -> bool:
    """推送消息到钉钉（支持Markdown格式）"""
    import requests

    try:
        # 钉钉机器人webhook格式: https://oapi.dingtalk.com/robot/send?access_token=***
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": "热点资讯",
                "text": content
            }
        }

        response = requests.post(webhook, json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json()
            return result.get("errcode", 0) == 0
        return False
    except Exception:
        logger.exception("钉钉推送失败")
        return False


def push_to_bark(webhook: str, content: str) -> bool:
    """推送消息到 Bark（iOS 推送）

    webhook 格式: https://api.day.app/XXXXXXXXX（保留或自定义 Bark 服务器地址）
    """
    import requests

    try:
        payload = {
            "title": "热点资讯",
            "body": content,
            "group": "hot-news",
            "icon": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f525.png",
        }
        response = requests.post(webhook, json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json()
            return result.get("code", 200) == 200
        return False
    except Exception:
        logger.exception("Bark 推送失败")
        return False


def _push_for_user(db: Session, config: UserConfig) -> tuple:
    """为单个用户执行推送。返回 (success: bool, message: str)"""
    if not config or not config.push_enabled or not config.push_webhook:
        return (False, "推送未启用或未配置Webhook")
    if not is_allowed_webhook(config.push_channel, config.push_webhook):
        return (False, "Webhook 地址不允许")

    user_id = config.user_id

    import json

    keywords = config.keywords or []
    if isinstance(keywords, str):
        keywords = json.loads(keywords) if keywords else []

    keyword_tags = config.keyword_tags or {}
    if isinstance(keyword_tags, str):
        keyword_tags = json.loads(keyword_tags) if keyword_tags else {}

    # 获取筛选后的新闻
    news_list, matched_keywords = database.get_user_filtered_news(db, user_id, keywords)

    seen_titles = set()
    unique_news = []
    for n in news_list:
        title = (n.title or "").strip()
        if title and title in seen_titles:
            continue
        if title:
            seen_titles.add(title)
        unique_news.append(n)
    news_list = unique_news

    if not news_list:
        return (False, "没有可推送的新闻")

    time_str = datetime.now().strftime('%H:%M')

    # 按标签分组
    keyword_to_tag = {}
    for tag, kws in keyword_tags.items():
        for kw in (kws or []):
            keyword_to_tag[kw.lower()] = tag

    tag_news = {}
    untagged = []
    for n in news_list:
        m_kws = matched_keywords.get(n.id, [])
        tag_found = None
        for kw in m_kws:
            tag = keyword_to_tag.get(kw.lower())
            if tag:
                tag_found = tag
                break
        if tag_found:
            tag_news.setdefault(tag_found, []).append((n, m_kws))
        else:
            untagged.append(n)

    # 生成 Markdown 内容（带超链接）
    content = f"📰 热点资讯 ({time_str})\n\n"
    if config.push_channel in ("dingtalk", "feishu", "bark"):
        for tag in sorted(tag_news.keys()):
            content += f"### {tag}\n"
            for i, (n, _) in enumerate(tag_news[tag], 1):
                content += f"{i}. [{n.platform}] [{n.title}]({n.url})\n"
            content += "\n"
        if untagged:
            content += "### 其他\n"
            for i, n in enumerate(untagged, 1):
                content += f"{i}. [{n.platform}] [{n.title}]({n.url})\n"
    else:
        for tag in sorted(tag_news.keys()):
            content += f"— {tag} —\n"
            for i, (n, _) in enumerate(tag_news[tag], 1):
                content += f"{i}. {n.title}\n"
            content += "\n"
        if untagged:
            content += "— 其他 —\n"
            for i, n in enumerate(untagged, 1):
                content += f"{i}. {n.title}\n"

    # 推送到对应渠道
    if config.push_channel == "feishu":
        success = push_to_feishu(config.push_webhook, content)
    elif config.push_channel == "dingtalk":
        success = push_to_dingtalk(config.push_webhook, content)
    elif config.push_channel == "bark":
        success = push_to_bark(config.push_webhook, content)
    else:
        return (False, f"不支持的推送渠道: {config.push_channel}")

    if success:
        return (True, f"成功推送{len(news_list)}条新闻")
    else:
        return (False, "推送失败")


# 推送失败退避状态（进程内存）：重启后丢失只会导致一次立即重试，安全性无影响。
# 多实例部署时可迁移到 Redis 共享。
_push_failures: Dict[int, tuple] = {}  # {user_id: (last_failure_at, fail_count)}


def _push_backoff_seconds(fail_count: int) -> int:
    """失败重试退避：1 分钟起步，指数增长，最多 1 小时。"""
    return min(3600, 60 * (2 ** min(fail_count, 6)))


def scheduled_push():
    """定时调度：遍历所有启用推送的用户，按各自 cron 表达式推送"""
    db = SessionLocal()
    try:
        configs = db.query(UserConfig).filter(UserConfig.push_enabled == True).all()
        if not configs:
            return
        now = datetime.now(UTC)
        for config in configs:
            if not config.push_webhook:
                continue
            # 解析用户的 cron 表达式
            cron_str = config.push_cron or "0 */4 * * *"
            try:
                trigger = CronTrigger.from_crontab(cron_str, timezone=UTC)
            except (ValueError, KeyError):
                logger.warning("⚠️ 用户%s cron 表达式无效: %s", config.user_id, cron_str)
                continue
            # 判断是否需要推送
            if config.last_push_at is None:
                should_push = True  # 首次推送
            else:
                last = config.last_push_at.replace(tzinfo=UTC)
                next_time = trigger.get_next_fire_time(last, now)
                should_push = next_time is not None and next_time <= now
            if should_push:
                failure = _push_failures.get(config.user_id)
                if failure:
                    last_fail, fail_count = failure
                    if (now - last_fail).total_seconds() < _push_backoff_seconds(fail_count):
                        continue
                try:
                    success, message = _push_for_user(db, config)
                except Exception:
                    logger.exception("❌ 定时推送 [用户%s] 异常", config.user_id)
                    fail_count = _push_failures.get(config.user_id, (now, 0))[1] + 1
                    _push_failures[config.user_id] = (now, fail_count)
                    continue
                logger.info("📬 定时推送 [用户%s] %s", config.user_id, message)
                if success:
                    # 数据库列统一存 naive UTC，与模型默认值保持一致
                    config.last_push_at = now.replace(tzinfo=None)
                    _push_failures.pop(config.user_id, None)
                    db.commit()
                else:
                    fail_count = _push_failures.get(config.user_id, (now, 0))[1] + 1
                    _push_failures[config.user_id] = (now, fail_count)
    except Exception:
        logger.exception("❌ 定时推送失败")
    finally:
        db.close()


@push_router.post("/api/push")
def push_news(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """手动触发推送"""
    config = db.query(UserConfig).filter(UserConfig.user_id == user_id).first()

    if not config or not config.push_enabled:
        return {"success": False, "error": "推送未启用"}

    if not config.push_webhook:
        return {"success": False, "error": "未配置Webhook"}

    success, message = _push_for_user(db, config)
    if success:
        return {"success": True, "message": message}
    else:
        return {"success": False, "error": message}
