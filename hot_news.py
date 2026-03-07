#!/usr/bin/env python3
"""
热点资讯系统
逻辑：
1. 爬虫获取各平台热点 → 缓存到 cache.json
2. 根据用户关键词过滤 → 返回个性化结果
3. 优先使用本地缓存（5分钟有效）
"""

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass, asdict
from typing import Optional

import requests
from bs4 import BeautifulSoup


# ========== 数据模型 ==========

@dataclass
class NewsItem:
    """新闻条目"""
    platform: str
    title: str
    url: str
    hot: str = ""
    time: str = ""


@dataclass
class UserConfig:
    """用户配置"""
    user_id: str
    username: str
    keywords: list
    blocked_keywords: list
    platforms: list
    push_enabled: bool = False


# ========== 缓存管理 ==========

CACHE_FILE = "cache.json"
USERS_FILE = "users.json"
CACHE_EXPIRE = 300  # 5分钟


def load_cache() -> dict:
    """加载缓存"""
    if not os.path.exists(CACHE_FILE):
        return {"timestamp": 0, "news": []}
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"timestamp": 0, "news": []}


def save_cache(news: list[NewsItem]):
    """保存缓存"""
    cache = {
        "timestamp": time.time(),
        "news": [asdict(item) for item in news]
    }
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def is_cache_valid() -> bool:
    """检查缓存是否有效"""
    cache = load_cache()
    return time.time() - cache.get("timestamp", 0) < CACHE_EXPIRE


# ========== 用户管理 ==========

def load_users() -> dict[str, UserConfig]:
    """加载用户配置"""
    if not os.path.exists(USERS_FILE):
        return {}
    
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    users = {}
    for user_id, info in data.items():
        config = info.get("config", {})
        users[user_id] = UserConfig(
            user_id=user_id,
            username=info.get("username", ""),
            keywords=config.get("keywords", []),
            blocked_keywords=config.get("blocked_keywords", []),
            platforms=config.get("platforms", []),
            push_enabled=config.get("push_enabled", False)
        )
    return users


# ========== 爬虫实现 ==========

class HotSpider:
    """热点爬虫基类"""
    
    name: str = ""
    
    def fetch(self) -> list[NewsItem]:
        """抓取热点"""
        raise NotImplementedError


class WeiboSpider(HotSpider):
    """微博热搜"""
    name = "weibo"
    COOKIE = "SUB=_2AkMWIuNSf8NxqwJRmP8dy2rhaoV2ygrEieKgfhKJJRMxHRl-yT9jqk86tRB6PaLNvQZR6zYUcYVT1zSjoSreQHidcUq7"
    
    def fetch(self) -> list[NewsItem]:
        url = "https://s.weibo.com/top/summary?cate=realtimehot"
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Cookie": self.COOKIE,
        })
        
        try:
            resp = session.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            rows = soup.select("#pl_top_realtimehot table tbody tr")
            
            items = []
            for row in rows[1:]:
                link = row.select_one("td.td-02 a")
                if not link:
                    continue
                href = link.get("href", "")
                if not href or "javascript" in href:
                    continue
                title = link.get_text(strip=True)
                if title:
                    items.append(NewsItem(
                        platform="微博",
                        title=title,
                        url=f"https://s.weibo.com{href}"
                    ))
            return items
        except Exception as e:
            print(f"❌ 微博: {e}")
            return []


class DouyinSpider(HotSpider):
    """抖音热搜"""
    name = "douyin"
    
    def fetch(self) -> list[NewsItem]:
        # 抖音需要更复杂的处理，暂时返回空
        return []


class BaiduSpider(HotSpider):
    """百度热搜"""
    name = "baidu"
    
    def fetch(self) -> list[NewsItem]:
        url = "https://top.baidu.com/board?tab=realtime"
        
        try:
            resp = requests.get(url, timeout=10)
            import re
            match = re.search(r'<!--s-data:(.*?)-->', resp.text, re.S)
            if not match:
                return []
            
            data = json.loads(match.group(1))
            items = []
            for item in data.get("data", {}).get("cards", [{}])[0].get("content", []):
                if item.get("isTop"):
                    continue
                items.append(NewsItem(
                    platform="百度",
                    title=item.get("word", ""),
                    url=item.get("rawUrl", "")
                ))
            return items
        except Exception as e:
            print(f"❌ 百度: {e}")
            return []


class BilibiliSpider(HotSpider):
    """B站热搜"""
    name = "bilibili"
    
    def fetch(self) -> list[NewsItem]:
        url = "https://api.bilibili.com/x/web-interface/popular"
        
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            items = []
            for item in data.get("data", {}).get("list", [])[:30]:
                items.append(NewsItem(
                    platform="B站",
                    title=item.get("title", ""),
                    url=f"https://www.bilibili.com/video/{item.get('bvid', '')}"
                ))
            return items
        except Exception as e:
            print(f"❌ B站: {e}")
            return []


# 注册爬虫
SPIDERS = {
    "weibo": WeiboSpider,
    "douyin": DouyinSpider,
    "baidu": BaiduSpider,
    "bilibili": BilibiliSpider,
}


# ========== 核心逻辑 ==========

def fetch_all_news(platforms: list[str] = None) -> list[NewsItem]:
    """获取所有平台的热点"""
    if platforms is None:
        platforms = list(SPIDERS.keys())
    
    all_news = []
    
    for platform in platforms:
        if platform not in SPIDERS:
            print(f"⚠️ 未知平台: {platform}")
            continue
        
        try:
            spider = SPIDERS[platform]()
            news = spider.fetch()
            print(f"✅ {spider.name}: 获取 {len(news)} 条")
            all_news.extend(news)
        except Exception as e:
            print(f"❌ {platform}: {e}")
    
    return all_news


# 兼容旧 API
fetch_all = fetch_all_news


def get_news_with_cache(platforms: list[str] = None) -> list[NewsItem]:
    """获取热点（优先使用缓存）"""
    if is_cache_valid():
        print("📦 使用缓存数据")
        cache = load_cache()
        return [NewsItem(**n) for n in cache.get("news", [])]
    else:
        print("🔄 缓存过期，正在更新...")
        return update_cache(platforms)


def filter_by_keywords(news: list, keywords: list, blocked: list = None) -> list:
    """按关键词过滤（兼容旧 API）"""
    if blocked is None:
        blocked = []
    
    result = []
    for item in news:
        title = item.title if hasattr(item, 'title') else item.get('title', '')
        
        # 跳过屏蔽词
        if any(b in title for b in blocked):
            continue
        
        # 匹配关键词（空关键词表示全部）
        if not keywords or any(k in title for k in keywords):
            result.append(item)
    
    return result


# 兼容 fetch_all_hot
fetch_all_hot = fetch_all_news


def update_cache(platforms: list[str] = None):
    """更新缓存"""
    print("🔄 正在抓取热点...")
    news = fetch_all_news(platforms)
    if news:
        save_cache(news)
        print(f"💾 已保存 {len(news)} 条到缓存")
    return news


def filter_news_by_user(news: list[NewsItem], user: UserConfig) -> list[NewsItem]:
    """根据用户配置过滤新闻"""
    result = []
    
    # 平台映射（小写名称 -> 中文名称）
    platform_map = {
        "weibo": "微博",
        "douyin": "抖音", 
        "baidu": "百度",
        "bilibili": "B站",
        "zhihu": "知乎",
        "toutiao": "头条",
        "36kr": "36Kr",
    }
    
    # 将用户平台转换为中文
    user_platforms_cn = []
    for p in user.platforms:
        user_platforms_cn.append(platform_map.get(p, p))
    
    # 先按平台过滤
    if user.platforms:
        news = [n for n in news if n.platform in user_platforms_cn]
    
    for item in news:
        title = item.title
        
        # 跳过屏蔽关键词
        if any(blocked in title for blocked in user.blocked_keywords):
            continue
        
        # 匹配关键词（空关键词表示全部）
        if not user.keywords:
            result.append(item)
        elif any(kw in title for kw in user.keywords):
            result.append(item)
    
    return result


def get_user_news(user_id: str) -> list[NewsItem]:
    """获取指定用户的热点（优先缓存）"""
    users = load_users()
    
    if user_id not in users:
        print(f"⚠️ 用户不存在: {user_id}")
        return []
    
    user = users[user_id]
    print(f"👤 用户: {user.username}, 关键词: {user.keywords}, 平台: {user.platforms}")
    
    # 优先使用缓存
    if is_cache_valid():
        print("📦 使用缓存数据")
        cache = load_cache()
        news = [NewsItem(**n) for n in cache.get("news", [])]
    else:
        print("🔄 缓存过期，正在更新...")
        news = update_cache(user.platforms)
    
    # 按用户关键词过滤
    filtered = filter_news_by_user(news, user)
    print(f"📋 匹配结果: {len(filtered)} 条")
    
    return filtered


def get_all_users_news() -> dict[str, list[NewsItem]]:
    """获取所有用户的个性化热点"""
    users = load_users()
    results = {}
    
    # 统一更新缓存
    if is_cache_valid():
        print("📦 使用缓存数据")
        cache = load_cache()
        all_news = [NewsItem(**n) for n in cache.get("news", [])]
    else:
        print("🔄 缓存过期，正在更新...")
        # 获取所有平台
        all_platforms = set()
        for user in users.values():
            all_platforms.update(user.platforms)
        all_news = update_cache(list(all_platforms)) if all_platforms else []
    
    # 分别过滤
    for user_id, user in users.items():
        results[user_id] = filter_news_by_user(all_news, user)
    
    return results


# ========== CLI 入口 ==========

def format_output(news: list[NewsItem], title: str = "热点资讯") -> str:
    """格式化输出"""
    lines = [f"# {title}", ""]
    
    # 按平台分组
    by_platform = {}
    for item in news:
        if item.platform not in by_platform:
            by_platform[item.platform] = []
        by_platform[item.platform].append(item)
    
    for platform, items in by_platform.items():
        lines.append(f"## {platform}")
        for i, item in enumerate(items[:10], 1):
            lines.append(f"{i}. {item.title}")
        lines.append("")
    
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="热点资讯系统")
    parser.add_argument("-u", "--user", help="用户ID")
    parser.add_argument("-a", "--all", action="store_true", help="获取所有用户")
    parser.add_argument("-f", "--force", action="store_true", help="强制刷新缓存")
    parser.add_argument("-o", "--output", help="输出文件")
    parser.add_argument("-s", "--sources", nargs="+", help="指定平台")
    
    args = parser.parse_args()
    
    # 强制刷新
    if args.force:
        print("🔄 强制刷新缓存...")
        update_cache(args.sources)
    
    if args.all:
        # 获取所有用户
        results = get_all_users_news()
        for user_id, news in results.items():
            users = load_users()
            user = users.get(user_id)
            username = user.username if user else user_id
            print(f"\n=== {username} ({len(news)}条) ===")
            for i, item in enumerate(news[:10], 1):
                print(f"  {i}. {item.title}")
    
    elif args.user:
        # 获取指定用户
        news = get_user_news(args.user)
        output = format_output(news, f"用户热点")
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output)
            print(f"📝 已保存到 {args.output}")
        else:
            print(output)
    
    else:
        # 默认：显示缓存状态
        cache = load_cache()
        age = time.time() - cache.get("timestamp", 0)
        print(f"缓存: {len(cache.get('news', []))} 条, {int(age)}秒前")
        
        if is_cache_valid():
            print("✅ 缓存有效")
        else:
            print("❌ 缓存已过期")
