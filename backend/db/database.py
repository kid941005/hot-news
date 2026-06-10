#!/usr/bin/env python3
"""
数据库操作
"""
import os
import base64
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from backend.models.models import News, User, UserConfig, CacheRecord, init_db


# ============= 新闻操作 =============

PLATFORM_MAP = {
    "weibo": "微博热搜",
    "baidu": "百度",
    "bilibili": "B站",
    "bilibili-hot-video": "B站热门视频",
    "bilibili-ranking": "B站排行榜",
    "douyin": "抖音",
    "zhihu": "知乎",
    "toutiao": "头条",
    "wallstreetcn": "华尔街见闻",
    "thepaper": "澎湃",
    "ifeng": "凤凰",
    "sspai": "少数派",
    "github": "GitHub",
    "cls": "财联社",
    "jin10": "金十数据",
    "zaobao": "联合早报",
    "gelonghui": "格隆汇",
    "fastbull": "法布财经",
    "pcbeta": "远景论坛",
    "ithome": "IT之家",
    "36kr": "36Kr",
    "36kr-renqi": "36氪人气榜",
    "xueqiu-hotstock": "雪球热门股票",
    "kuaishou": "快手",
    "tencent": "腾讯新闻",
    "kaopu": "靠谱新闻",
    "cankaoxiaoxi": "参考消息",
    "hupu": "虎扑",
    "tieba": "百度贴吧",
}

def save_news(db: Session, news_list: List[dict]):
    """批量保存新闻"""
    if not news_list:
        return

    platform = news_list[0].get('platform', '')
    cutoff = datetime.utcnow() - timedelta(days=7)
    
    # 仅清理 7 天前旧数据，保留近 7 天历史新闻
    db.query(News).filter(News.platform == platform, News.created_at < cutoff).delete()
    
    # 写入新数据
    try:
        for item in news_list:
            existing = db.query(News).filter(
                News.platform == item.get('platform', ''),
                News.title == item.get('title', ''),
                News.url == item.get('url', ''),
            ).first()
            if isinstance(existing, News):
                existing.hot_value = item.get('hot', '')
                existing.pub_time = item.get('time', '')
                existing.raw_data = item
                existing.updated_at = datetime.utcnow()
                continue
            news = News(
                platform=item.get('platform', ''),
                title=item.get('title', ''),
                url=item.get('url', ''),
                hot_value=item.get('hot', ''),
                pub_time=item.get('time', ''),
                raw_data=item
            )
            db.add(news)
        db.commit()
    except Exception:
        db.rollback()
        raise


def get_all_news(db: Session, platforms: List[str] = None) -> List[News]:
    """获取所有新闻"""
    # 转换英文平台名为中文
    if platforms:
        chinese_platforms = []
        for p in platforms:
            if p in PLATFORM_MAP:
                chinese_platforms.append(PLATFORM_MAP[p])
            else:
                chinese_platforms.append(p)
        platforms = chinese_platforms
    
    query = db.query(News)
    if platforms:
        query = query.filter(News.platform.in_(platforms))
    return query.order_by(News.id.desc()).all()


def get_user_filtered_news(db: Session, user_id: int, filter_keywords: List[str] = None) -> tuple:
    """获取用户过滤后的新闻
    filter_keywords: 可选的关键词列表，用于按标签筛选
    返回: (新闻列表, {news_id: [匹配的关键词列表]})
    """
    config = db.query(UserConfig).filter(UserConfig.user_id == user_id).first()
    if not config:
        return get_all_news(db), {}
    
    # 将用户平台转换为中文
    user_platforms = config.platforms if config.platforms else None
    if user_platforms:
        if isinstance(user_platforms, str):
            import json
            user_platforms = json.loads(user_platforms)
        db_platforms = [PLATFORM_MAP.get(p, p) for p in user_platforms]
    else:
        db_platforms = None
    
    # 获取基础新闻
    all_news = get_all_news(db, db_platforms)
    
    # 关键词过滤
    result = []
    matched_keywords = {}  # {news_id: [匹配的关键词]}
    
    # 如果指定了filter_keywords（按标签筛选），优先使用；即使为空列表也使用（空标签 = 全部匹配）
    if filter_keywords is not None:
        keywords = filter_keywords
    else:
        keywords = config.keywords or []
    
    blocked = config.blocked_keywords or []
    
    # 解析JSON字符串
    import json
    if isinstance(keywords, str):
        keywords = json.loads(keywords) if keywords else []
    if isinstance(blocked, str):
        blocked = json.loads(blocked) if blocked else []
    
    for news in all_news:
        title = news.title
        
        # 跳过屏蔽词（忽略大小写）
        title_lower = title.lower()
        if any(b.lower() in title_lower for b in blocked):
            continue
        
        # 匹配关键词（忽略大小写，空关键词表示全部）
        matched_kws = []
        if not keywords or any(k.lower() in title_lower for k in keywords):
            # 找出具体匹配了哪些关键词
            if keywords:
                for k in keywords:
                    if k.lower() in title_lower:
                        matched_kws.append(k)
            result.append(news)
            matched_keywords[news.id] = matched_kws
    
    return result, matched_keywords


# ============= 用户操作 =============

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return "pbkdf2_sha256$100000$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, stored_hash: str) -> bool:
    if stored_hash.startswith("pbkdf2_sha256$"):
        _, iterations, salt_b64, digest_b64 = stored_hash.split("$", 3)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    actual_hash = hashlib.sha256(password.encode()).hexdigest()
    return hmac.compare_digest(actual_hash, stored_hash)


def create_user(db: Session, username: str, password: str) -> User:
    """创建用户"""
    password_hash = hash_password(password)
    
    user = User(username=username, password_hash=password_hash)
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # 创建默认配置
    config = UserConfig(user_id=user.id)
    db.add(config)
    db.commit()
    
    return user


def verify_user(db: Session, username: str, password: str) -> Optional[User]:
    """验证用户"""
    user = db.query(User).filter(User.username == username).first()
    if user and verify_password(password, user.password_hash):
        return user
    return None


def get_user_config(db: Session, user_id: int) -> Optional[UserConfig]:
    """获取用户配置"""
    return db.query(UserConfig).filter(UserConfig.user_id == user_id).first()


def update_user_config(db: Session, user_id: int, config_data: dict) -> UserConfig:
    """更新用户配置"""
    config = db.query(UserConfig).filter(UserConfig.user_id == user_id).first()
    
    if not config:
        config = UserConfig(user_id=user_id)
        db.add(config)
    
    if 'keywords' in config_data:
        config.keywords = config_data['keywords']
    if 'blocked_keywords' in config_data:
        config.blocked_keywords = config_data['blocked_keywords']
    if 'keyword_tags' in config_data:
        config.keyword_tags = config_data['keyword_tags']
    if 'platforms' in config_data:
        config.platforms = config_data['platforms']
    if 'push_enabled' in config_data:
        config.push_enabled = config_data['push_enabled']
    if 'push_channel' in config_data:
        config.push_channel = config_data['push_channel']
    if 'push_webhook' in config_data:
        config.push_webhook = config_data['push_webhook']
    if 'push_cron' in config_data:
        config.push_cron = config_data['push_cron']
    
    config.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(config)
    
    return config


# ============= 缓存操作 =============

def update_cache_record(db: Session, platform: str, status: str, error: str = ""):
    """更新缓存记录"""
    record = db.query(CacheRecord).filter(CacheRecord.platform == platform).first()
    now = datetime.now()
    
    if not record:
        record = CacheRecord(platform=platform)
        db.add(record)
    
    record.last_fetch = now
    record.status = status
    record.last_status = status
    record.error_msg = error
    if status == "success":
        record.last_success_at = now
    elif status == "error":
        record.last_error_at = now
    db.commit()


def get_cache_status(db: Session) -> List[CacheRecord]:
    """获取缓存状态"""
    return db.query(CacheRecord).all()
