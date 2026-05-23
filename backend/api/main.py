#!/usr/bin/env python3
"""
FastAPI 应用 - 带Vue3前端
"""
import os
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session

from backend.models.models import init_db, get_db, UserConfig, ensure_user_config_schema, SessionLocal
from backend.db import database
from backend.db.database import PLATFORM_MAP
from backend.spiders import spiders
from backend.models.models import News

from datetime import timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = BackgroundScheduler()
UTC = timezone.utc
REFRESH_INTERVAL_MINUTES = int(os.environ.get("REFRESH_INTERVAL_MINUTES", "15"))
PUSH_INTERVAL_HOURS = int(os.getenv("PUSH_INTERVAL_HOURS", "4"))

app = FastAPI(title="热点资讯", version="2.0")

# 静态文件路径
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============= 数据模型 =============

class LoginRequest(BaseModel):
    username: str
    password: str


class ConfigRequest(BaseModel):
    keywords: Optional[List[str]] = None
    blocked_keywords: Optional[List[str]] = None
    keyword_tags: Optional[dict] = None  # 关键词标签映射
    platforms: Optional[List[str]] = None
    push_enabled: Optional[bool] = None
    push_channel: Optional[str] = None
    push_webhook: Optional[str] = None
    push_cron: Optional[str] = None  # cron 表达式，如 "0 */4 * * *"


# ============= 依赖 =============

# Token 认证
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict

# 简单的 token 存储 (生产环境应该用数据库或 Redis)
_tokens: Dict[str, tuple] = {}  # {token: (user_id, expires_at)}

def generate_token(user_id: int, expires_hours: int = 24 * 7) -> str:
    """生成 token"""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=expires_hours)
    _tokens[token] = (user_id, expires_at)
    return token

def verify_token(token: str) -> Optional[int]:
    """验证 token，返回 user_id"""
    if not token or token not in _tokens:
        return None
    user_id, expires_at = _tokens[token]
    if datetime.now() > expires_at:
        del _tokens[token]
        return None
    return user_id

def delete_token(token: str):
    """删除 token"""
    if token in _tokens:
        del _tokens[token]

def get_optional_user_id(Authorization: Optional[str] = Header(None)) -> Optional[int]:
    """获取可选用户ID - 无有效 token 时返回 None"""
    if Authorization and Authorization.startswith("Bearer "):
        token = Authorization[7:]
        return verify_token(token)
    return None


def get_current_user_id(Authorization: Optional[str] = Header(None)) -> int:
    """获取当前用户ID - 从 Authorization header 获取 token"""
    user_id = get_optional_user_id(Authorization)
    if user_id:
        return user_id
    raise HTTPException(status_code=401, detail="未认证")


# ============= 前端页面 =============

FALLBACK_PAGE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>热点资讯</title></head>
<body>
    <h1>前端静态文件未构建</h1>
    <p>请先在 frontend 目录运行 npm run build，并将构建产物部署到 backend/api/static。</p>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return FALLBACK_PAGE


# ============= API接口 =============

@app.post("/api/register")
def register(req: LoginRequest, db: Session = Depends(get_db)):
    try:
        user = database.create_user(db, req.username, req.password)
        token = generate_token(user.id)
        return {"success": True, "username": user.username, "user_id": user.id, "token": token}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = database.verify_user(db, req.username, req.password)
    if user:
        token = generate_token(user.id)
        return {"success": True, "username": user.username, "user_id": user.id, "token": token}
    return {"success": False, "error": "用户名或密码错误"}


@app.post("/api/logout")
def logout(Authorization: Optional[str] = Header(None)):
    if Authorization and Authorization.startswith("Bearer "):
        token = Authorization[7:]
        delete_token(token)
    return {"success": True}


@app.get("/api/platforms")
def get_platforms():
    return {
        "success": True,
        "platforms": [{"id": k, "name": v} for k, v in PLATFORM_MAP.items()]
    }


@app.get("/api/config")
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
            "last_push_at": config.last_push_at.isoformat() + "Z" if config.last_push_at else None,
        }
    }


@app.get("/api/tags")
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
    
    import json
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


@app.post("/api/config")
def update_config(req: ConfigRequest, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    config_data = req.dict(exclude_unset=True)
    database.update_user_config(db, user_id, config_data)
    return {"success": True}


# ============= 推送功能 =============

def push_to_feishu(webhook: str, content: str) -> bool:
    """推送消息到飞书（支持Markdown格式）"""
    import requests
    
    # 飞书机器人webhook格式: https://open.feishu.cn/open-apis/bot/v2/hook/xxx
    try:
        # 构建消息体
        payload = {
            "msg_type": "markdown",
            "content": {
                "text": content
            }
        }
        
        response = requests.post(webhook, json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json()
            return result.get("code", 0) == 0
        return False
    except Exception as e:
        print(f"飞书推送失败: {e}")
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
    except Exception as e:
        print(f"钉钉推送失败: {e}")
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
    except Exception as e:
        print(f"Bark 推送失败: {e}")
        return False


def _push_for_user(db: Session, config: UserConfig) -> tuple:
    """为单个用户执行推送。返回 (success: bool, message: str)"""
    if not config or not config.push_enabled or not config.push_webhook:
        return (False, "推送未启用或未配置Webhook")

    user_id = config.user_id

    # 获取筛选后的新闻
    news_list, matched_keywords = database.get_user_filtered_news(db, user_id, config.keywords or [])

    # 过滤屏蔽词
    if config.blocked_keywords:
        news_list = [n for n in news_list if not any(kw in n.title for kw in config.blocked_keywords)]

    # 取最新10条
    news_list = news_list[:10]

    if not news_list:
        return (False, "没有可推送的新闻")

    from datetime import datetime
    time_str = datetime.now().strftime('%H:%M')

    # 按标签分组
    keyword_tags = config.keyword_tags or {}
    keyword_to_tag = {}
    for tag, kws in keyword_tags.items():
        for kw in (kws or []):
            keyword_to_tag[kw.lower()] = tag

    tag_news = {}
    untagged = []
    for n in news_list:
        m_kws = matched_keywords.get(n.id, [])
        tags_found = set()
        for kw in m_kws:
            tag = keyword_to_tag.get(kw.lower())
            if tag:
                tags_found.add(tag)
        if tags_found:
            for tag in tags_found:
                tag_news.setdefault(tag, []).append((n, m_kws))
        else:
            untagged.append(n)

    # 生成 Markdown 内容（带超链接）
    content = f"📰 热点资讯 ({time_str})\n\n"
    if config.push_channel in ("dingtalk", "feishu", "bark"):
        for tag in sorted(tag_news.keys()):
            content += f"### {tag}\n"
            for i, (n, _) in enumerate(tag_news[tag], 1):
                content += f"{i}. [{n.title}]({n.url})\n"
            content += "\n"
        if untagged:
            content += "### 其他\n"
            for i, n in enumerate(untagged, 1):
                content += f"{i}. [{n.title}]({n.url})\n"
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


def scheduled_refresh():
    """独立定时刷新新闻数据"""
    from backend.models.models import SessionLocal
    db = SessionLocal()
    try:
        saved_count = refresh_news_data(db)
        global LAST_REFRESH_TIME
        LAST_REFRESH_TIME = datetime.now(timezone.utc)
        print(f"🔄 定时刷新完成，共保存 {saved_count} 条新闻")
    except Exception as e:
        print(f"❌ 定时刷新失败: {e}")
    finally:
        db.close()


def scheduled_push():
    """定时调度：遍历所有启用推送的用户，按各自 cron 表达式推送"""
    from backend.models.models import SessionLocal
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
                print(f"⚠️ 用户{config.user_id} cron 表达式无效: {cron_str}")
                continue
            # 判断是否需要推送
            if config.last_push_at is None:
                should_push = True  # 首次推送
            else:
                last = config.last_push_at.replace(tzinfo=UTC)
                next_time = trigger.get_next_fire_time(last, now)
                should_push = next_time is not None and next_time <= now
            if should_push:
                refresh_news_data(db)
                success, message = _push_for_user(db, config)
                print(f"📬 定时推送 [用户{config.user_id}] {message}")
                if success:
                    config.last_push_at = now
                    db.commit()
    except Exception as e:
        print(f"❌ 定时推送失败: {e}")
    finally:
        db.close()


@app.on_event("startup")
def start_scheduler():
    """启动定时任务调度器"""
    scheduler.add_job(scheduled_refresh, 'interval', minutes=REFRESH_INTERVAL_MINUTES, id='refresh_job')
    scheduler.add_job(scheduled_push, 'interval', minutes=1, id='push_job')
    scheduler.start()
    print(f"⏰ 定时刷新已启动（每 {REFRESH_INTERVAL_MINUTES} 分钟抓取一次）")
    print("⏰ 定时推送已启动（每分钟检查 cron 表达式）")


@app.on_event("shutdown")
def stop_scheduler():
    """关闭定时推送调度器"""
    scheduler.shutdown(wait=False)
    print("⏰ 定时推送已关闭")


@app.post("/api/push")
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
    
    refresh_news_data(db)
    success, message = _push_for_user(db, config)
    if success:
        return {"success": True, "message": message}
    else:
        return {"success": False, "error": message}


@app.get("/api/news")
def get_news(
    tag: str = None,  # 标签筛选
    today: bool = False,  # 是否只显示当天入库的文章
    all: bool = False,  # 获取所有热榜，不按关键词过滤
    user_id: int = Depends(get_current_user_id), 
    db: Session = Depends(get_db)
):
    config = db.query(UserConfig).filter(UserConfig.user_id == user_id).first()
    
    # 如果指定了all=true，获取所有热榜（不按关键词过滤）
    if all:
        news_list = database.get_all_news(db)
        matched_keywords = {}
    elif tag and config and config.keyword_tags is not None:
        # 如果指定了标签，使用该标签的关键词
        import json
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
    
    # 可选过滤当天入库的文章并按时间倒序
    today_str = datetime.now().strftime("%Y-%m-%d")
    news_data = []
    for n in news_list:
        if today and n.created_at:
            if n.created_at.strftime("%Y-%m-%d") != today_str:
                continue
        
        item = n.to_dict()
        # 标记匹配的关键词
        item['matched_keywords'] = matched_keywords.get(n.id, [])
        news_data.append(item)
    
    # 按时间倒序排列
    news_data.sort(key=lambda x: x.get('pub_time', ''), reverse=True)

    keyword_groups = {}
    if tag and config and config.keyword_tags is not None:
        for item in news_data:
            item_keywords = item.get('matched_keywords', []) or []
            for kw in item_keywords:
                keyword_groups.setdefault(kw, []).append(item)
    
    return {
        "success": True,
        "news": news_data,
        "keyword_groups": keyword_groups,
        "total": len(news_data),
        "current_tag": tag
    }


@app.get("/api/news/by_platform")
def get_news_by_platform(
    user_id: Optional[int] = Depends(get_optional_user_id),
    db: Session = Depends(get_db)
):
    """按平台分组获取新闻；未登录时返回公共全平台数据"""
    config = db.query(UserConfig).filter(UserConfig.user_id == user_id).first() if user_id else None
    
    # 获取用户监控的平台
    user_platforms = config.platforms if config and config.platforms else None
    if user_platforms:
        if isinstance(user_platforms, str):
            import json
            user_platforms = json.loads(user_platforms)
        # 转换为中文平台名
        chinese_platforms = [PLATFORM_MAP.get(p, p) for p in user_platforms]
    else:
        chinese_platforms = list(PLATFORM_MAP.values())
    
    # 按平台分组获取新闻
    platform_news = {}
    for platform in chinese_platforms:
        news_items = db.query(News).filter(News.platform == platform).order_by(News.id.desc()).all()
        items = [n.to_dict() for n in news_items]
        if items:
            platform_news[platform] = items[:10]  # 每个平台最多10条
    
    return {
        "success": True,
        "platforms": platform_news
    }


from datetime import datetime, timezone

LAST_REFRESH_TIME = None

def refresh_news_data(db: Session, results: dict = None):
    if results is None:
        results = awaitable_fetch_all_spiders()
    saved_count = 0
    for platform, news in results.items():
        if news:
            try:
                database.save_news(db, news)
                saved_count += len(news)
                print(f"✅ 保存 {platform}: {len(news)} 条")
            except Exception as e:
                print(f"❌ 保存失败 {platform}: {e}")
    return saved_count


def awaitable_fetch_all_spiders():
    import asyncio
    return asyncio.run(spiders.fetch_all_spiders())


@app.post("/api/news/refresh")
async def refresh_news(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    global LAST_REFRESH_TIME
    try:
        results = await spiders.fetch_all_spiders()
        saved_count = refresh_news_data(db, results)
        print(f"📊 共保存 {saved_count} 条新闻")
        LAST_REFRESH_TIME = datetime.now(timezone.utc)
        return {"success": True, "last_refresh": LAST_REFRESH_TIME.isoformat().replace("+00:00", "Z"), "count": saved_count}
    except Exception as e:
        print(f"❌ 刷新失败: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/news/refresh")
def get_refresh_time():
    global LAST_REFRESH_TIME
    if LAST_REFRESH_TIME:
        return {
            "success": True,
            "last_refresh": LAST_REFRESH_TIME.isoformat().replace("+00:00", "Z"),
            "display": LAST_REFRESH_TIME.strftime("%H:%M")
        }
    return {"success": True, "last_refresh": None}


@app.on_event("startup")
def startup():
    init_db()
    ensure_user_config_schema()
    # 挂载静态文件
    if os.path.exists(STATIC_DIR):
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=16888)
