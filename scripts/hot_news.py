#!/usr/bin/env python3
"""
Hot News Aggregator - 热点资讯聚合工具
支持多平台热点聚合 + 关键词过滤 + 推送通知
"""

import os
import sys
import json
import time
import hashlib
import urllib.request
import ssl
from datetime import datetime
from urllib.parse import urlencode

# SSL context
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Data storage
DATA_DIR = os.path.expanduser("~/.openclaw/workspace/hot-news")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
CACHE_FILE = os.path.join(DATA_DIR, "cache.json")

os.makedirs(DATA_DIR, exist_ok=True)

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def load_config():
    default = {
        "keywords": [],  # 用户关键词
        "blocked_keywords": [],  # 屏蔽关键词
        "push_enabled": False,
        "push_channel": "feishu",  # feishu, dingtalk, webhook
        "push_webhook": ""
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return {**default, **json.load(f)}
    return default

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# ============== 热点数据源 ==============

def fetch_weibo_hot():
    """获取微博热搜"""
    try:
        url = "https://weibo.com/ajax/side/hotSearch"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            results = []
            for item in data.get('data', {}).get('realtime', [])[:20]:
                results.append({
                    'platform': '微博',
                    'title': item.get('word', ''),
                    'hot': item.get('num', 0),
                    'url': f"https://s.weibo.com/weibo?q={item.get('word', '')}",
                    'time': datetime.now().strftime("%H:%M")
                })
            return results
    except Exception as e:
        print(f"微博热搜获取失败: {e}")
        return []

def fetch_baidu_hot():
    """获取百度热搜"""
    try:
        url = "https://top.baidu.com/board?tab=realtime"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            html = response.read().decode('utf-8')
            import re
            results = []
            # 简单解析
            pattern = r'"topic-name":"([^"]+)".*?"hot-score":(\d+)'
            matches = re.findall(pattern, html)[:20]
            for title, hot in matches:
                results.append({
                    'platform': '百度',
                    'title': title,
                    'hot': int(hot),
                    'url': f"https://www.baidu.com/s?wd={title}",
                    'time': datetime.now().strftime("%H:%M")
                })
            return results
    except Exception as e:
        print(f"百度热搜获取失败: {e}")
        return []

def fetch_zhihu_hot():
    """获取知乎热榜"""
    try:
        url = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=20"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            results = []
            for item in data.get('data', [])[:20]:
                results.append({
                    'platform': '知乎',
                    'title': item.get('target', {}).get('title_area', {}).get('text', ''),
                    'hot': item.get('detail_text', ''),
                    'url': "https://www.zhihu.com" + item.get('target', {}).get('link', {}).get('url', ''),
                    'time': datetime.now().strftime("%H:%M")
                })
            return results
    except Exception as e:
        print(f"知乎热榜获取失败: {e}")
        return []

def fetch_toutiao_hot():
    """获取头条热搜"""
    try:
        url = "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao&_signature="
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            results = []
            for item in data.get('data', [])[:20]:
                results.append({
                    'platform': '头条',
                    'title': item.get('Title', ''),
                    'hot': item.get('HotValue', 0),
                    'url': "https://www.toutiao.com" + item.get('Link', ''),
                    'time': datetime.now().strftime("%H:%M")
                })
            return results
    except Exception as e:
        print(f"头条热搜获取失败: {e}")
        return []

def fetch_douyin_hot():
    """获取抖音热榜"""
    try:
        url = "https://www.douyin.com/aweme/v1/web/hot/search/list/"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            results = []
            for item in data.get('data', {}).get('word_list', [])[:20]:
                results.append({
                    'platform': '抖音',
                    'title': item.get('word', ''),
                    'hot': item.get('hot_value', 0),
                    'url': f"https://www.douyin.com/search/{item.get('word', '')}",
                    'time': datetime.now().strftime("%H:%M")
                })
            return results
    except Exception as e:
        print(f"抖音热榜获取失败: {e}")
        return []

def fetch_bilibili_hot():
    """获取B站热搜"""
    try:
        url = "https://api.bilibili.com/x/web-interface/popular?pn=0&ps=20"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            results = []
            for item in data.get('data', {}).get('list', [])[:20]:
                results.append({
                    'platform': 'B站',
                    'title': item.get('title', ''),
                    'hot': item.get('desc', ''),
                    'url': "https://www.bilibili.com/video/" + item.get('bvid', ''),
                    'time': datetime.now().strftime("%H:%M")
                })
            return results
    except Exception as e:
        print(f"B站热搜获取失败: {e}")
        return []

def fetch_36kr_hot():
    """获取36Kr热搜"""
    try:
        url = "https://36kr.com/napi/newsflash"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            results = []
            for item in data.get('data', [])[:20]:
                results.append({
                    'platform': '36Kr',
                    'title': item.get('title', ''),
                    'hot': '',
                    'url': "https://36kr.com/news/" + item.get('item_id', ''),
                    'time': datetime.now().strftime("%H:%M")
                })
            return results
    except Exception as e:
        print(f"36Kr获取失败: {e}")
        return []

def fetch_jinri_hot():
    """获取今日头条热搜"""
    try:
        url = "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            results = []
            for item in data.get('data', [])[:20]:
                results.append({
                    'platform': '今日头条',
                    'title': item.get('Title', ''),
                    'hot': item.get('HotValue', 0),
                    'url': "https://www.toutiao.com" + item.get('Link', ''),
                    'time': datetime.now().strftime("%H:%M")
                })
            return results
    except Exception as e:
        print(f"今日头条获取失败: {e}")
        return []

# ============== 核心功能 ==============

def fetch_all_hot(platforms=None):
    """获取所有平台热点"""
    all_news = []
    
    fetchers = {
        'weibo': fetch_weibo_hot,
        'baidu': fetch_baidu_hot,
        'zhihu': fetch_zhihu_hot,
        'toutiao': fetch_toutiao_hot,
        'douyin': fetch_douyin_hot,
        'bilibili': fetch_bilibili_hot,
        '36kr': fetch_36kr_hot,
        'jinri': fetch_jinri_hot
    }
    
    if platforms is None:
        platforms = fetchers.keys()
    
    for platform in platforms:
        if platform in fetchers:
            try:
                news = fetchers[platform]()
                all_news.extend(news)
                print(f"获取 {platform} 成功: {len(news)} 条")
            except Exception as e:
                print(f"获取 {platform} 失败: {e}")
    
    # 按热度排序
    all_news.sort(key=lambda x: x.get('hot', 0), reverse=True)
    
    return all_news

def filter_by_keywords(news, keywords=None, blocked=None):
    """根据关键词过滤新闻"""
    if not keywords and not blocked:
        return news
    
    filtered = []
    for item in news:
        title = item.get('title', '')
        
        # 检查屏蔽词
        if blocked:
            if any(b in title for b in blocked):
                continue
        
        # 检查关键词（如果没有设置关键词，则返回所有）
        if keywords:
            if any(k in title for k in keywords):
                filtered.append(item)
        else:
            filtered.append(item)
    
    return filtered

def push_to_feishu(webhook, content):
    """推送到飞书"""
    if not webhook:
        return False
    
    try:
        data = {
            "msg_type": "text",
            "content": {"text": content}
        }
        req = urllib.request.Request(
            webhook,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            return response.status == 200
    except Exception as e:
        print(f"飞书推送失败: {e}")
        return False

def push_to_webhook(url, content):
    """推送到自定义Webhook"""
    if not url:
        return False
    
    try:
        data = {"content": content}
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            return response.status == 200
    except Exception as e:
        print(f"Webhook推送失败: {e}")
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser(description='热点资讯聚合工具')
    parser.add_argument('--fetch', action='store_true', help='获取所有热点')
    parser.add_argument('--platforms', nargs='+', help='指定平台: weibo baidu zhihu toutiao douyin bilibili 36kr')
    parser.add_argument('--keywords', nargs='+', help='关键词过滤')
    parser.add_argument('--blocked', nargs='+', help='屏蔽关键词')
    parser.add_argument('--limit', type=int, default=50, help='返回数量')
    parser.add_argument('--push', action='store_true', help='推送最新热点')
    
    args = parser.parse_args()
    
    if args.fetch:
        # 获取热点
        news = fetch_all_hot(args.platforms)
        news = filter_by_keywords(news, args.keywords, args.blocked)
        news = news[:args.limit]
        
        print(json.dumps(news, ensure_ascii=False, indent=2))
        
    elif args.push:
        # 推送到配置渠道
        config = load_config()
        
        if not config.get('push_enabled'):
            print("推送未启用")
            return
        
        news = fetch_all_hot()
        news = filter_by_keywords(news, config.get('keywords'), config.get('blocked_keywords'))
        news = news[:10]
        
        # 生成推送内容
        content = f"📰 热点资讯 ({datetime.now().strftime('%H:%M')})\n\n"
        for i, item in enumerate(news, 1):
            content += f"{i}. {item['title']}\n"
        
        # 推送
        if config.get('push_channel') == 'feishu':
            push_to_feishu(config.get('push_webhook'), content)
        else:
            push_to_webhook(config.get('push_webhook'), content)
        
        print("推送完成")
    
    else:
        # 默认显示帮助
        parser.print_help()

if __name__ == '__main__':
    main()
