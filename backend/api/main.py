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

from backend.models.models import init_db, get_db, UserConfig
from backend.db import database
from backend.db.database import PLATFORM_MAP
from backend.spiders import spiders
from backend.models.models import News

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


# ============= 依赖 =============

# Token 认证
import secrets
from datetime import datetime, timedelta
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
        }
    }


@app.get("/api/tags")
def get_tags(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """获取用户的标签列表"""
    config = database.get_user_config(db, user_id)
    if not config or not config.keyword_tags:
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
    """推送消息到飞书"""
    import requests
    
    # 飞书机器人webhook格式: https://open.feishu.cn/open-apis/bot/v2/hook/xxx
    try:
        # 构建消息体
        payload = {
            "msg_type": "text",
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
    """推送消息到钉钉"""
    import requests
    
    try:
        # 钉钉机器人webhook格式: https://oapi.dingtalk.com/robot/send?access_token=xxx
        payload = {
            "msgtype": "text",
            "text": {
                "content": content
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
    
    # 获取筛选后的新闻
    news_list, _ = database.get_user_filtered_news(db, user_id, config.keywords or [])
    
    # 过滤屏蔽词
    if config.blocked_keywords:
        news_list = [n for n in news_list if not any(kw in n.title for kw in config.blocked_keywords)]
    
    # 取最新10条
    news_list = news_list[:10]
    
    if not news_list:
        return {"success": False, "error": "没有可推送的新闻"}
    
    # 生成内容
    from datetime import datetime
    content = f"📰 热点资讯 ({datetime.now().strftime('%H:%M')})\n\n"
    for i, item in enumerate(news_list, 1):
        content += f"{i}. {item.title}\n"
        if i >= 10:
            break
    
    # 推送到对应渠道
    if config.push_channel == "feishu":
        success = push_to_feishu(config.push_webhook, content)
    elif config.push_channel == "dingtalk":
        success = push_to_dingtalk(config.push_webhook, content)
    else:
        return {"success": False, "error": f"不支持的推送渠道: {config.push_channel}"}
    
    if success:
        return {"success": True, "message": f"成功推送{len(news_list)}条新闻"}
    else:
        return {"success": False, "error": "推送失败"}


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
    elif tag and config and config.keyword_tags:
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
    
    return {
        "success": True,
        "news": news_data,
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

@app.post("/api/news/refresh")
async def refresh_news(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    global LAST_REFRESH_TIME
    try:
        results = await spiders.fetch_all_spiders()
        saved_count = 0
        for platform, news in results.items():
            if news:
                try:
                    database.save_news(db, news)
                    saved_count += len(news)
                    print(f"✅ 保存 {platform}: {len(news)} 条")
                except Exception as e:
                    print(f"❌ 保存失败 {platform}: {e}")
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
    # 挂载静态文件
    if os.path.exists(STATIC_DIR):
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=16888)
