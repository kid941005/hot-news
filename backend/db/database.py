#!/usr/bin/env python3
"""
数据库操作
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from backend.models.models import News, User, UserConfig, CacheRecord, init_db


# ============= 新闻操作 =============

def save_news(db: Session, news_list: List[dict]):
    """批量保存新闻"""
    platform = news_list[0].get('platform', '') if news_list else ''
    
    # 清理旧数据
    db.query(News).filter(News.platform == platform).delete()
    
    # 写入新数据
    for item in news_list:
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


def get_all_news(db: Session, platforms: List[str] = None) -> List[News]:
    """获取所有新闻"""
    # 平台名称映射: 英文ID -> 中文
    platform_map = {
        "weibo": "微博",
        "baidu": "百度",
        "bilibili": "B站",
        "douyin": "抖音",
        "zhihu": "知乎",
        "toutiao": "头条",
        "wallstreetcn": "华尔街见闻",
        "thepaper": "澎湃",
        "ifeng": "凤凰",
        "sspai": "少数派",
        "v2ex": "V2EX",
        "jin10": "金十数据",
        "ithome": "IT之家",
        "36kr": "36Kr",
    }
    
    # 转换英文平台名为中文
    if platforms:
        chinese_platforms = []
        for p in platforms:
            if p in platform_map:
                chinese_platforms.append(platform_map[p])
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
    
    # 平台名称映射: 英文ID -> 中文
    platform_map = {
        "weibo": "微博",
        "baidu": "百度",
        "bilibili": "B站",
        "douyin": "抖音",
        "zhihu": "知乎",
        "toutiao": "头条",
        "wallstreetcn": "华尔街见闻",
        "thepaper": "澎湃",
        "ifeng": "凤凰",
        "sspai": "少数派",
        "v2ex": "V2EX",
        "jin10": "金十数据",
        "ithome": "IT之家",
        "36kr": "36Kr",
    }
    
    # 将用户平台转换为中文
    user_platforms = config.platforms if config.platforms else None
    if user_platforms:
        if isinstance(user_platforms, str):
            import json
            user_platforms = json.loads(user_platforms)
        db_platforms = [platform_map.get(p, p) for p in user_platforms]
    else:
        db_platforms = None
    
    # 获取基础新闻
    all_news = get_all_news(db, db_platforms)
    
    # 关键词过滤
    result = []
    matched_keywords = {}  # {news_id: [匹配的关键词]}
    
    # 如果指定了filter_keywords（按标签筛选），优先使用；否则使用用户配置的关键词
    if filter_keywords is not None and len(filter_keywords) > 0:
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

def create_user(db: Session, username: str, password: str) -> User:
    """创建用户"""
    import hashlib
    
    # 简单密码哈希
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
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
    import hashlib
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    user = db.query(User).filter(User.username == username).first()
    if user and user.password_hash == password_hash:
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
    
    config.updated_at = datetime.now()
    db.commit()
    db.refresh(config)
    
    return config


# ============= 缓存操作 =============

def update_cache_record(db: Session, platform: str, status: str, error: str = ""):
    """更新缓存记录"""
    record = db.query(CacheRecord).filter(CacheRecord.platform == platform).first()
    
    if not record:
        record = CacheRecord(platform=platform)
        db.add(record)
    
    record.last_fetch = datetime.now()
    record.status = status
    record.error_msg = error
    db.commit()


def get_cache_status(db: Session) -> List[CacheRecord]:
    """获取缓存状态"""
    return db.query(CacheRecord).all()
