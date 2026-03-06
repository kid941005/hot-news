#!/usr/bin/env python3
"""
热点资讯后端 - 核心功能：关键词过滤 + 缓存
"""

import os
import sys
import json
import urllib.request
import ssl
import re
from datetime import datetime
from urllib.parse import quote

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://weibo.com'
}

# 缓存配置
CACHE_DIR = os.path.expanduser("~/.openclaw/workspace/hot-news")
CACHE_FILE = os.path.join(CACHE_DIR, "cache.json")
CACHE_EXPIRE = 3600  # 缓存1小时

os.makedirs(CACHE_DIR, exist_ok=True)

def fetch(url, timeout=10):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))

# ============== 缓存管理 ==============

def load_cache():
    """加载缓存"""
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('news', [])
    except:
        pass
    return None

def save_cache(news):
    """保存缓存 - 合并新旧数据"""
    try:
        # 加载已有缓存
        existing = []
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    existing = json.load(f).get('news', [])
            except:
                pass
        
        # 合并去重
        existing_dict = {n.get('title', ''): n for n in existing}
        for n in news:
            title = n.get('title', '')
            if title and title not in existing_dict:
                existing_dict[title] = n
        
        merged = list(existing_dict.values())
        
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().timestamp(),
                'news': merged
            }, f, ensure_ascii=False)
    except Exception as e:
        print(f"缓存保存失败: {e}")

# ============== 数据源 ==============

def fetch_weibo():
    """微博热搜"""
    try:
        data = fetch("https://weibo.com/ajax/side/hotSearch")
        return [{
            'platform': '微博',
            'title': i.get('word', ''),
            'hot': i.get('num', 0),
            'url': f"https://s.weibo.com/weibo?q={quote(i.get('word', ''))}",
            'time': datetime.now().strftime("%H:%M")
        } for i in data.get('data', {}).get('realtime', [])[:30]]
    except Exception as e:
        print(f"微博失败: {e}")
        return []

def fetch_baidu():
    """百度热搜"""
    try:
        req = urllib.request.Request("https://top.baidu.com/board?tab=realtime", headers=HEADERS)
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            html = resp.read().decode('utf-8')
            matches = re.findall(r'"content_(\d+)":\s*\{[^}]*"title":"([^"]+)"[^}]*"hotScore":(\d+)', html)
            if matches:
                return [{
                    'platform': '百度',
                    'title': t,
                    'hot': int(h) if h.isdigit() else 0,
                    'url': f"https://www.baidu.com/s?wd={quote(t)}",
                    'time': datetime.now().strftime("%H:%M")
                } for _, t, h in matches[:30]]
            words = re.findall(r'"word":"([^"]+)"', html)[:30]
            return [{'platform': '百度', 'title': w, 'hot': '', 'url': f"https://www.baidu.com/s?wd={quote(w)}", 'time': datetime.now().strftime("%H:%M")} for w in words]
    except Exception as e:
        print(f"百度失败: {e}")
        return []

def fetch_zhihu():
    """知乎热榜"""
    try:
        data = fetch("https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=30")
        return [{
            'platform': '知乎',
            'title': i.get('target', {}).get('title_area', {}).get('text', ''),
            'hot': i.get('detail_text', ''),
            'url': "https://www.zhihu.com" + i.get('target', {}).get('link', {}).get('url', ''),
            'time': datetime.now().strftime("%H:%M")
        } for i in data.get('data', [])[:30]]
    except Exception as e:
        print(f"知乎失败: {e}")
        return []

def fetch_douyin():
    """抖音热榜"""
    try:
        url = "https://www.douyin.com/aweme/v1/web/hot/search/list/"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15',
            'Referer': 'https://www.douyin.com/'
        })
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return [{
                'platform': '抖音',
                'title': i.get('word', ''),
                'hot': i.get('hot_value', 0),
                'url': f"https://www.douyin.com/search/{quote(i.get('word', ''))}",
                'time': datetime.now().strftime("%H:%M")
            } for i in data.get('data', {}).get('word_list', [])[:30]]
    except Exception as e:
        print(f"抖音失败: {e}")
        return []

def fetch_bilibili():
    """B站热搜"""
    try:
        data = fetch("https://api.bilibili.com/x/web-interface/popular?pn=0&ps=30")
        return [{
            'platform': 'B站',
            'title': i.get('title', ''),
            'hot': i.get('desc', ''),
            'url': "https://www.bilibili.com/video/" + i.get('bvid', ''),
            'time': datetime.now().strftime("%H:%M")
        } for i in data.get('data', {}).get('list', [])[:30]]
    except Exception as e:
        print(f"B站失败: {e}")
        return []

def fetch_toutiao():
    """今日头条热搜"""
    try:
        req = urllib.request.Request(
            "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc",
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return [{
                'platform': '头条',
                'title': i.get('Title', ''),
                'hot': i.get('HotValue', ''),
                'url': i.get('Url', ''),
                'time': datetime.now().strftime("%H:%M")
            } for i in data.get('data', [])[:30]]
    except Exception as e:
        print(f"头条失败: {e}")
        return []

def fetch_tieba():
    """百度贴吧热议"""
    try:
        data = fetch("https://tieba.baidu.com/hottopic/browse/topicList")
        results = []
        for i in data.get('data', {}).get('bang_topic', {}).get('topic_list', [])[:30]:
            if i.get('topic_name'):
                # 转换时间戳
                create_ts = i.get('create_time', 0)
                if create_ts:
                    try:
                        from datetime import datetime
                        time_str = datetime.fromtimestamp(create_ts).strftime("%m-%d %H:%M")
                    except:
                        time_str = datetime.now().strftime("%H:%M")
                else:
                    time_str = datetime.now().strftime("%H:%M")
                
                results.append({
                    'platform': '贴吧',
                    'title': i.get('topic_name', ''),
                    'hot': '',
                    'url': i.get('topic_url', ''),
                    'time': time_str
                })
        return results
    except Exception as e:
        print(f"贴吧失败: {e}")
        return []

def fetch_ithome():
    """IT之家热榜"""
    try:
        req = urllib.request.Request(
            "https://www.ithome.com/list/",
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            html = resp.read().decode('utf-8')
            import re
            # 解析标题、链接和时间
            items = re.findall(r'<a class="t" href="([^"]+)"[^>]*>([^<]+)</a>.*?<i>([^<]+)</i>', html, re.S)
            results = []
            for url, title, time_str in items[:30]:
                if title and not any(k in title for k in ['优惠', '促销', '广告']):
                    # 简化时间格式
                    time_str = time_str.strip()
                    if ' ' in time_str:
                        time_str = time_str.split(' ')[1][:5]  # 取 HH:MM
                    results.append({
                        'platform': 'IT之家',
                        'title': title.strip(),
                        'hot': '',
                        'url': 'https://www.ithome.com' + url,
                        'time': time_str
                    })
            return results
    except Exception as e:
        print(f"IT之家失败: {e}")
        return []

def fetch_36kr():
    """36氪快讯"""
    try:
        data = fetch("https://36kr.com/napi/newsflash")
        results = []
        for i in data.get('data', {}).get('items', [])[:30]:
            if i.get('title'):
                # 转换时间戳
                published = i.get('published_at', '')
                if published:
                    try:
                        from datetime import datetime
                        ts = int(published)
                        time_str = datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")
                    except:
                        time_str = published[:16]
                else:
                    time_str = datetime.now().strftime("%H:%M")
                
                results.append({
                    'platform': '36Kr',
                    'title': i.get('title', ''),
                    'hot': '',
                    'url': 'https://36kr.com/news/' + str(i.get('id', '')),
                    'time': time_str
                })
        return results
    except Exception as e:
        print(f"36Kr失败: {e}")
        return []

# 平台映射
PLATFORMS = {
    'weibo': ('微博', fetch_weibo),
    'baidu': ('百度', fetch_baidu),
    'zhihu': ('知乎', fetch_zhihu),
    'douyin': ('抖音', fetch_douyin),
    'bilibili': ('B站', fetch_bilibili),
    'toutiao': ('今日头条', fetch_toutiao),
    'tieba': ('贴吧', fetch_tieba),
    'ithome': ('IT之家', fetch_ithome),
    '36kr': ('36Kr', fetch_36kr),
}

# ============== 核心功能 ==============

def fetch_all(platforms=None, use_cache=True):
    """获取所有平台热点 - 带缓存"""
    # 优先使用缓存
    if use_cache:
        cached = load_cache()
        if cached:
            print(f"使用缓存: {len(cached)} 条")
            return cached
    
    all_news = []
    success_count = 0
    
    if platforms is None:
        platforms = list(PLATFORMS.keys())
    
    for p in platforms:
        if p in PLATFORMS:
            try:
                _, fetcher = PLATFORMS[p]
                news = fetcher()
                if news:
                    all_news.extend(news)
                    success_count += 1
                    print(f"✓ {p}: {len(news)} 条")
                else:
                    print(f"✗ {p}: 无数据")
            except Exception as e:
                print(f"✗ {p}: {e}")
    
    # 排序
    def get_hot(x):
        h = x.get('hot', 0)
        if isinstance(h, str):
            return 0
        return h
    
    all_news.sort(key=get_hot, reverse=True)
    
    # 保存缓存
    if all_news:
        save_cache(all_news)
    else:
        # 失败时使用缓存
        cached = load_cache()
        if cached:
            print(f"API失败，使用缓存: {len(cached)} 条")
            return cached
    
    return all_news

def filter_by_keywords(news, keywords=None, blocked=None):
    """关键词过滤"""
    if not keywords and not blocked:
        return news
    
    result = []
    for item in news:
        title = item.get('title', '')
        
        if blocked and any(b in title for b in blocked):
            continue
        
        if keywords:
            if any(k in title for k in keywords):
                result.append(item)
        else:
            result.append(item)
    
    return result
