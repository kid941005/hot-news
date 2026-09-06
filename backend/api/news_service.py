#!/usr/bin/env python3
"""
新闻模块：新闻查询、去重、按平台分组与自动/手动刷新。
"""
import asyncio
import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.api import scheduler_service
from backend.api.auth import get_current_user_id, get_optional_user_id
from backend.config import get_env_int
from backend.db import database
from backend.db.database import PLATFORM_MAP
from backend.models.models import News, SessionLocal, UserConfig, get_db
from backend.spiders import spiders

logger = logging.getLogger(__name__)

news_router = APIRouter()

REFRESH_COOLDOWN_SECONDS = get_env_int("REFRESH_COOLDOWN_SECONDS", 300, min_value=0, max_value=86400)
AUTO_REFRESH_COOLDOWN_SECONDS = get_env_int("AUTO_REFRESH_COOLDOWN_SECONDS", 30, min_value=5, max_value=3600)

LAST_REFRESH_TIME = None
REFRESH_LOCK = asyncio.Lock()
_auto_refresh_running = False
_auto_refresh_platforms = set()
_AUTO_REFRESH_LOCK = threading.Lock()


def _deduplicate_news_by_title(news_list):
    seen_titles = set()
    unique_news = []
    for news in news_list:
        title = (getattr(news, "title", "") or "").strip().casefold()
        if title and title in seen_titles:
            continue
        if title:
            seen_titles.add(title)
        unique_news.append(news)
    return unique_news


def _append_keyword_group_once(keyword_groups, item, item_keywords, seen_titles):
    """每条新闻只归入首个匹配关键词组，避免跨组重复展示。"""
    if not item_keywords:
        return
    title = (item.get("title") or "").strip().casefold()
    kw = item_keywords[0]
    if title and title in seen_titles:
        return
    keyword_groups.setdefault(kw, []).append(item)
    if title:
        seen_titles.add(title)


def _created_at_to_local(value):
    """将数据库中的 naive UTC 时间转为服务器本地时区。"""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone()


@news_router.get("/api/news")
def get_news(
    tag: str = None,  # 标签筛选
    today: bool = False,  # 是否只显示当天入库的文章
    all: bool = False,  # 获取所有热榜，不按关键词过滤
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    config = db.query(UserConfig).filter(UserConfig.user_id == user_id).first()
    user_platforms = config.platforms if config and config.platforms else None
    _trigger_auto_refresh_if_needed(db, user_platforms)
    state = _get_refresh_state(db, user_platforms)
    if state.get("stale") and not state.get("refreshing"):
        _wait_for_auto_refresh(db)
        state = _get_refresh_state(db, user_platforms)

    # 如果指定了all=true，获取所有热榜（不按关键词过滤）
    if all:
        news_list = database.get_all_news(db)
        matched_keywords = {}
    elif tag and config and config.keyword_tags is not None:
        # 如果指定了标签，使用该标签的关键词
        if isinstance(config.keyword_tags, str):
            keyword_tags = json.loads(config.keyword_tags)
        else:
            keyword_tags = config.keyword_tags

        # 直接获取该标签对应的关键词列表
        filter_keywords = keyword_tags.get(tag, [])
        news_list, matched_keywords = database.get_user_filtered_news(db, user_id, filter_keywords)
    else:
        # 默认按用户关键词过滤
        news_list, matched_keywords = database.get_user_filtered_news(db, user_id)
    news_list = _deduplicate_news_by_title(news_list)

    # 标签页只展示当天入库的匹配新闻；旧新闻对关键词标签页没有意义
    today_only = today or bool(tag)
    today_local = datetime.now().astimezone().date()
    news_data = []
    for n in news_list:
        if today_only and n.created_at:
            created_local = _created_at_to_local(n.created_at)
            if created_local is None or created_local.date() != today_local:
                continue

        item = n.to_dict()
        # 标记匹配的关键词
        item['matched_keywords'] = matched_keywords.get(n.id, [])
        news_data.append(item)

    # 按时间倒序排列：优先使用平台发布时间，缺失时回退到入库时间
    def _news_sort_key(item):
        pub_time = item.get('pub_time') or ''
        return (bool(pub_time), pub_time, item.get('created_at') or '')
    news_data.sort(key=_news_sort_key, reverse=True)

    keyword_groups = {}
    seen_group_titles = set()
    if tag and config and config.keyword_tags is not None:
        for item in news_data:
            item_keywords = item.get('matched_keywords', []) or []
            _append_keyword_group_once(keyword_groups, item, item_keywords, seen_group_titles)

    return {
        "success": True,
        "news": news_data,
        "keyword_groups": keyword_groups,
        "total": len(news_data),
        "current_tag": tag,
        **state,
    }


@news_router.get("/api/news/by_platform")
def get_news_by_platform(
    user_id: Optional[int] = Depends(get_optional_user_id),
    db: Session = Depends(get_db),
    limit_per_platform: int = Query(50, ge=1, le=100),
    sort: str = Query("rank"),
):
    """按平台分组获取新闻；未登录时返回公共全平台数据"""
    config = db.query(UserConfig).filter(UserConfig.user_id == user_id).first() if user_id else None

    # 获取用户监控的平台
    user_platforms = config.platforms if config and config.platforms else None
    if user_platforms:
        if isinstance(user_platforms, str):
            user_platforms = json.loads(user_platforms)
        # 转换为中文平台名
        chinese_platforms = [PLATFORM_MAP.get(p, p) for p in user_platforms]
    else:
        chinese_platforms = list(PLATFORM_MAP.values())
    refresh_platforms = _normalize_platforms(chinese_platforms)
    _trigger_auto_refresh_if_needed(db, refresh_platforms)
    state = _get_refresh_state(db, refresh_platforms)
    if state.get("stale") and not state.get("refreshing"):
        _wait_for_auto_refresh(db)
        state = _get_refresh_state(db, refresh_platforms)

    # 按平台分组获取新闻
    platform_news = {}
    for platform in chinese_platforms:
        order = News.created_at.desc() if sort == "timeline" else News.id.asc()
        news_items = db.query(News).filter(News.platform == platform).order_by(order).limit(limit_per_platform).all()
        items = [n.to_dict() for n in news_items]
        if items:
            platform_news[platform] = items

    return {
        "success": True,
        "platforms": platform_news,
        **state,
    }


def _normalize_platforms(platforms=None):
    if platforms is None:
        return list(spiders.SPIDERS.keys())
    if isinstance(platforms, str):
        platforms = [platforms]
    reverse_map = {value: key for key, value in PLATFORM_MAP.items()}
    return [reverse_map.get(platform, platform) for platform in platforms if platform]


def _is_cache_stale(record) -> bool:
    last_refresh = getattr(record, "last_success_at", None) or getattr(record, "last_fetch", None)
    if not isinstance(last_refresh, datetime):
        return True
    if last_refresh.tzinfo is None:
        last_refresh = last_refresh.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - last_refresh.astimezone(timezone.utc)).total_seconds() >= AUTO_REFRESH_COOLDOWN_SECONDS


def _get_stale_platforms(db: Session, platforms=None):
    stale_platforms = []
    for platform in _normalize_platforms(platforms):
        record = db.query(database.CacheRecord).filter(database.CacheRecord.platform == platform).first()
        if record is None or _is_cache_stale(record):
            stale_platforms.append(platform)
    return stale_platforms


def _get_refresh_state(db: Session, platforms=None) -> dict:
    def format_time(value):
        if not value:
            return None
        if isinstance(value, datetime):
            return value.isoformat().replace("+00:00", "Z")
        return str(value)

    latest_cache = None
    try:
        query = db.query(database.CacheRecord)
        if hasattr(query, "order_by"):
            query = query.order_by(database.CacheRecord.last_fetch.desc())
        latest_cache = query.first()
    except Exception:
        latest_cache = None
    last_refresh = LAST_REFRESH_TIME or (latest_cache.last_fetch if latest_cache else None)
    last_refresh_text = format_time(last_refresh)
    stale_platforms = _get_stale_platforms(db, platforms)
    requested_platforms = _normalize_platforms(platforms)
    refreshing = _auto_refresh_running or REFRESH_LOCK.locked() or bool(_auto_refresh_platforms.intersection(requested_platforms))
    sources = {}
    for platform in requested_platforms:
        record = db.query(database.CacheRecord).filter(database.CacheRecord.platform == platform).first()
        if not record:
            sources[platform] = {"status": "missing"}
            continue
        sources[platform] = {
            "status": getattr(record, "last_status", None) or getattr(record, "status", ""),
            "last_fetch": format_time(getattr(record, "last_fetch", None)),
            "last_success_at": format_time(getattr(record, "last_success_at", None)),
            "last_error_at": format_time(getattr(record, "last_error_at", None)),
            "error": getattr(record, "error_msg", ""),
        }
    return {
        "last_refresh": last_refresh_text,
        "refreshing": refreshing,
        "stale": bool(stale_platforms),
        "stale_platforms": stale_platforms,
        "sources": sources,
    }


def _run_background_refresh(platforms=None):
    global LAST_REFRESH_TIME, _auto_refresh_running, _auto_refresh_platforms
    platforms = _normalize_platforms(platforms)
    try:
        db = SessionLocal()
        try:
            results = asyncio.run(spiders.fetch_all_spiders(platforms))
            saved_count, sources = refresh_news_data(db, results)
            LAST_REFRESH_TIME = datetime.now(timezone.utc)
            logger.info("📊 后台自动刷新 %s: 共保存 %s 条新闻", ",".join(platforms), saved_count)
        finally:
            db.close()
    except Exception:
        logger.exception("❌ 后台自动刷新失败")
    finally:
        with _AUTO_REFRESH_LOCK:
            _auto_refresh_platforms.difference_update(platforms)
            _auto_refresh_running = bool(_auto_refresh_platforms)


def _wait_for_auto_refresh(db: Session, timeout_seconds: float = 8.0) -> None:
    if timeout_seconds <= 0:
        return
    deadline = datetime.now(timezone.utc).timestamp() + timeout_seconds
    while datetime.now(timezone.utc).timestamp() < deadline:
        if not _auto_refresh_running and not REFRESH_LOCK.locked():
            return
        time.sleep(0.2)


def _trigger_auto_refresh_if_needed(db: Session, platforms=None):
    global _auto_refresh_running, LAST_REFRESH_TIME, _auto_refresh_platforms
    stale_platforms = [platform for platform in _get_stale_platforms(db, platforms) if platform not in _auto_refresh_platforms]
    if not stale_platforms:
        return
    with _AUTO_REFRESH_LOCK:
        # 在锁内二次过滤，避免并发请求重复刷新同一批平台
        stale_platforms = [platform for platform in stale_platforms if platform not in _auto_refresh_platforms]
        if not stale_platforms:
            return
        has_data = db.query(News).first() is not None
        if not has_data:
            # 没有数据时同步刷新（用户等待）
            logger.info("🔄 数据库为空，触发同步刷新: %s", ",".join(stale_platforms))
            try:
                results = asyncio.run(spiders.fetch_all_spiders(stale_platforms))
                saved_count, sources = refresh_news_data(db, results)
                LAST_REFRESH_TIME = datetime.now(timezone.utc)
                logger.info("📊 同步刷新完成: 共保存 %s 条新闻", saved_count)
            except Exception:
                logger.exception("❌ 同步刷新失败")
            return
        # 有数据但过期：后台异步刷新
        logger.info("🔄 数据过期，触发后台自动刷新: %s", ",".join(stale_platforms))
        _auto_refresh_platforms.update(stale_platforms)
        _auto_refresh_running = True
        t = threading.Thread(target=_run_background_refresh, args=(stale_platforms,), daemon=True)
        t.start()


def refresh_news_data(db: Session, results: dict = None, platforms=None):
    # per-source cache: 每个源写入 CacheRecord，供前端和刷新状态使用
    if results is None:
        results = awaitable_fetch_all_spiders(platforms)
    saved_count = 0
    sources = {}
    for platform, news in results.items():
        if news:
            try:
                database.save_news(db, news)
                database.update_cache_record(db, platform, "success")
                saved_count += len(news)
                sources[platform] = {"status": "success", "count": len(news)}
                logger.info("✅ 保存 %s: %s 条", platform, len(news))
            except Exception as e:
                database.update_cache_record(db, platform, "error", str(e))
                sources[platform] = {"status": "error", "count": 0, "error": str(e)}
                logger.exception("❌ 保存失败 %s", platform)
        else:
            database.update_cache_record(db, platform, "empty")
            sources[platform] = {"status": "empty", "count": 0}
    return saved_count, sources


def awaitable_fetch_all_spiders(platforms=None):
    return asyncio.run(spiders.fetch_all_spiders(_normalize_platforms(platforms)))


def scheduled_refresh():
    """独立定时刷新新闻数据"""
    global LAST_REFRESH_TIME
    db = SessionLocal()
    try:
        saved_count, _ = refresh_news_data(db)
        LAST_REFRESH_TIME = datetime.now(timezone.utc)
        logger.info("🔄 定时刷新完成，共保存 %s 条新闻", saved_count)
        scheduler_service.mark_job_run("refresh_job", True, f"共保存 {saved_count} 条新闻")
    except Exception:
        logger.exception("❌ 定时刷新失败")
        scheduler_service.mark_job_run("refresh_job", False, "定时刷新失败")
    finally:
        db.close()


@news_router.post("/api/news/refresh")
async def refresh_news(
    platform: Optional[str] = Query(None),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    global LAST_REFRESH_TIME
    now = datetime.now(timezone.utc)
    platforms = _normalize_platforms(platform)
    if REFRESH_LOCK.locked():
        return {"success": False, "error": "刷新正在进行中"}
    if not platform and LAST_REFRESH_TIME and REFRESH_COOLDOWN_SECONDS > 0:
        elapsed = (now - LAST_REFRESH_TIME).total_seconds()
        if elapsed < REFRESH_COOLDOWN_SECONDS:
            return {
                "success": False,
                "error": f"刷新太频繁，请等待 {int(REFRESH_COOLDOWN_SECONDS - elapsed)} 秒",
                "last_refresh": LAST_REFRESH_TIME.isoformat().replace("+00:00", "Z"),
            }
    async with REFRESH_LOCK:
        try:
            results = await spiders.fetch_all_spiders(platforms)
            saved_count, sources = refresh_news_data(db, results)
            logger.info("📊 共保存 %s 条新闻", saved_count)
            LAST_REFRESH_TIME = datetime.now(timezone.utc)
            return {"success": True, "last_refresh": LAST_REFRESH_TIME.isoformat().replace("+00:00", "Z"), "count": saved_count, "sources": sources}
        except Exception as e:
            logger.exception("❌ 刷新失败")
            return {"success": False, "error": str(e)}


@news_router.get("/api/news/refresh")
def get_refresh_time(db: Session = Depends(get_db)):
    global LAST_REFRESH_TIME
    if LAST_REFRESH_TIME:
        return {
            "success": True,
            "last_refresh": LAST_REFRESH_TIME.isoformat().replace("+00:00", "Z"),
            "display": LAST_REFRESH_TIME.strftime("%H:%M")
        }
    latest = db.query(News).order_by(News.updated_at.desc()).first()
    if latest and latest.updated_at:
        return {
            "success": True,
            "last_refresh": latest.updated_at.isoformat() + "Z",
            "display": latest.updated_at.strftime("%H:%M")
        }
    return {"success": True, "last_refresh": None}
