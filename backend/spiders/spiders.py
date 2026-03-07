#!/usr/bin/env python3
"""
爬虫模块 - 扩展版
"""
import json
import re
import requests
from bs4 import BeautifulSoup
from typing import List
from datetime import datetime


class BaseSpider:
    """爬虫基类"""
    name = ""
    
    def fetch(self) -> List[dict]:
        raise NotImplementedError


class WeiboSpider(BaseSpider):
    """微博热搜"""
    name = "weibo"
    COOKIE = "SUB=_2AkMWIuNSf8NxqwJRmP8dy2rhaoV2ygrEieKgfhKJJRMxHRl-yT9jqk86tRB6PaLNvQZR6zYUcYVT1zSjoSreQHidcUq7"
    
    def fetch(self) -> List[dict]:
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
                    items.append({
                        "platform": "微博",
                        "title": title,
                        "url": f"https://s.weibo.com{href}",
                        "hot": "",
                        "time": datetime.now().strftime("%H:%M")
                    })
            return items
        except Exception as e:
            print(f"❌ 微博: {e}")
            return []


class BaiduSpider(BaseSpider):
    """百度热搜"""
    name = "baidu"
    
    def fetch(self) -> List[dict]:
        url = "https://top.baidu.com/board?tab=realtime"
        
        try:
            resp = requests.get(url, timeout=10)
            match = re.search(r'<!--s-data:(.*?)-->', resp.text, re.S)
            if not match:
                return []
            
            data = json.loads(match.group(1))
            items = []
            for item in data.get("data", {}).get("cards", [{}])[0].get("content", []):
                if item.get("isTop"):
                    continue
                items.append({
                    "platform": "百度",
                    "title": item.get("word", ""),
                    "url": item.get("rawUrl", ""),
                    "hot": "",
                    "time": datetime.now().strftime("%H:%M")
                })
            return items
        except Exception as e:
            print(f"❌ 百度: {e}")
            return []


class BilibiliSpider(BaseSpider):
    """B站热搜"""
    name = "bilibili"
    
    def fetch(self) -> List[dict]:
        url = "https://api.bilibili.com/x/web-interface/popular"
        
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            items = []
            for item in data.get("data", {}).get("list", [])[:30]:
                items.append({
                    "platform": "B站",
                    "title": item.get("title", ""),
                    "url": f"https://www.bilibili.com/video/{item.get('bvid', '')}",
                    "hot": str(item.get("play", 0)),
                    "time": datetime.now().strftime("%H:%M")
                })
            return items
        except Exception as e:
            print(f"❌ B站: {e}")
            return []


class DouyinSpider(BaseSpider):
    """抖音热搜"""
    name = "douyin"
    
    def fetch(self) -> List[dict]:
        return []


class ZhihuSpider(BaseSpider):
    """知乎热榜"""
    name = "zhihu"
    
    def fetch(self) -> List[dict]:
        url = "https://api.zhihu.com/topstory/hot-lists/total"
        
        try:
            resp = requests.get(url, timeout=10, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            data = resp.json()
            items = []
            for item in data.get("data", [])[:30]:
                target = item.get("target", {})
                items.append({
                    "platform": "知乎",
                    "title": target.get("title", ""),
                    "url": target.get("url", ""),
                    "hot": str(item.get("detail_text", "")),
                    "time": datetime.now().strftime("%H:%M")
                })
            return items
        except Exception as e:
            print(f"❌ 知乎: {e}")
            return []


class ToutiaoSpider(BaseSpider):
    """头条热搜"""
    name = "toutiao"
    
    def fetch(self) -> List[dict]:
        url = "https://www.toutiao.com/api/pc/feed/?category=news_hot&max_behot_time=0"
        
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            items = []
            for item in data.get("data", []):
                if item.get("media_name"):
                    items.append({
                        "platform": "头条",
                        "title": item.get("title", ""),
                        "url": f"https://www.toutiao.com{a}" if (a := item.get("url")) else "",
                        "hot": str(item.get("read_count", "")),
                        "time": datetime.now().strftime("%H:%M")
                    })
            return items
        except Exception as e:
            print(f"❌ 头条: {e}")
            return []


class WallstreetcnSpider(BaseSpider):
    """华尔街见闻"""
    name = "wallstreetcn"
    
    def fetch(self) -> List[dict]:
        url = "https://api.iostink.cn/ws/hot/rank?code=wallstreetcn"
        
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            items = []
            for item in data.get("data", [])[:30]:
                items.append({
                    "platform": "华尔街见闻",
                    "title": item.get("title", ""),
                    "url": f"https://wallstreetcn.com/news/{item.get('id', '')}",
                    "hot": str(item.get("hot", "")),
                    "time": datetime.now().strftime("%H:%M")
                })
            return items
        except Exception as e:
            print(f"❌ 华尔街见闻: {e}")
            return []


class ThepaperSpider(BaseSpider):
    """澎湃新闻"""
    name = "thepaper"
    
    def fetch(self) -> List[dict]:
        url = "https://www.thepaper.cn/ajax/getDetail recommendList"
        
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            items = []
            for item in data.get("recommendList", [])[:30]:
                items.append({
                    "platform": "澎湃",
                    "title": item.get("title", ""),
                    "url": f"https://www.thepaper.cn/detail_{item.get('id', '')}",
                    "hot": "",
                    "time": datetime.now().strftime("%H:%M")
                })
            return items
        except Exception as e:
            print(f"❌ 澎湃: {e}")
            return []


class IfengSpider(BaseSpider):
    """凤凰网"""
    name = "ifeng"
    
    def fetch(self) -> List[dict]:
        url = "https://news.ifeng.com/feed"
        
        try:
            resp = requests.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            items = []
            for item in soup.select(".box_01 .news_list li")[:20]:
                link = item.select_one("a")
                if link:
                    title = link.get_text(strip=True)
                    if title:
                        items.append({
                            "platform": "凤凰",
                            "title": title,
                            "url": "https://news.ifeng.com" + link.get("href", ""),
                            "hot": "",
                            "time": datetime.now().strftime("%H:%M")
                        })
            return items
        except Exception as e:
            print(f"❌ 凤凰: {e}")
            return []


class SspaiSpider(BaseSpider):
    """少数派"""
    name = "sspai"
    
    def fetch(self) -> List[dict]:
        url = "https://sspai.com/api/v1/articles?limit=20&offset=0&sort=hot"
        
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            items = []
            for item in data.get("data", []):
                items.append({
                    "platform": "少数派",
                    "title": item.get("title", ""),
                    "url": f"https://sspai.com/post/{item.get('id', '')}",
                    "hot": str(item.get("likes", 0)),
                    "time": datetime.now().strftime("%H:%M")
                })
            return items
        except Exception as e:
            print(f"❌ 少数派: {e}")
            return []


class V2exSpider(BaseSpider):
    """V2EX"""
    name = "v2ex"
    
    def fetch(self) -> List[dict]:
        url = "https://www.v2ex.com/?tab=hot"
        
        try:
            resp = requests.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            items = []
            for item in soup.select(".item_hot_topic")[:20]:
                link = item.select_one("a")
                if link:
                    title = link.get_text(strip=True)
                    if title:
                        items.append({
                            "platform": "V2EX",
                            "title": title,
                            "url": "https://www.v2ex.com" + link.get("href", ""),
                            "hot": "",
                            "time": datetime.now().strftime("%H:%M")
                        })
            return items
        except Exception as e:
            print(f"❌ V2EX: {e}")
            return []


class GitHubSpider(BaseSpider):
    """GitHubTrending"""
    name = "github"
    
    def fetch(self) -> List[dict]:
        url = "https://api.github.com/search/repositories?q=created:>2024-01-01&sort=stars&order=desc"
        
        try:
            resp = requests.get(url, timeout=10, headers={"Accept": "application/vnd.github.v3+json"})
            data = resp.json()
            items = []
            for item in data.get("items", [])[:20]:
                items.append({
                    "platform": "GitHub",
                    "title": item.get("name", ""),
                    "url": item.get("html_url", ""),
                    "hot": str(item.get("stargazers_count", 0)),
                    "time": datetime.now().strftime("%H:%M")
                })
            return items
        except Exception as e:
            print(f"❌ GitHub: {e}")
            return []


class Jin10Spider(BaseSpider):
    """金十数据"""
    name = "jin10"
    
    def fetch(self) -> List[dict]:
        url = "https://flash-api.jin10.com/get_flash_list"
        
        try:
            resp = requests.get(url, timeout=10, headers={
                "x-app-id": "b593066b2fcf4506b4e5",
                "x-version": "1.0.0"
            })
            data = resp.json()
            items = []
            for item in data.get("data", [])[:30]:
                items.append({
                    "platform": "金十数据",
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "hot": str(item.get("time", "")),
                    "time": datetime.now().strftime("%H:%M")
                })
            return items
        except Exception as e:
            print(f"❌ 金十数据: {e}")
            return []


class IthomeSpider(BaseSpider):
    """IT之家"""
    name = "ithome"
    
    def fetch(self) -> List[dict]:
        url = "https://www.ithome.com/Ranking"
        
        try:
            resp = requests.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            items = []
            for item in soup.select(".item-post")[:20]:
                link = item.select_one("a")
                if link:
                    title = link.get_text(strip=True)
                    if title:
                        href = link.get("href", "")
                        items.append({
                            "platform": "IT之家",
                            "title": title,
                            "url": href if href.startswith("http") else f"https://www.ithome.com{href}",
                            "hot": "",
                            "time": datetime.now().strftime("%H:%M")
                        })
            return items
        except Exception as e:
            print(f"❌ IT之家: {e}")
            return []


class Kr36Spider(BaseSpider):
    """36Kr"""
    name = "36kr"
    
    def fetch(self) -> List[dict]:
        url = "https://36kr.com/pp/api/pc/feed"
        
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            items = []
            for item in data.get("data", {}).get("items", [])[:20]:
                items.append({
                    "platform": "36Kr",
                    "title": item.get("title", ""),
                    "url": f"https://36kr.com{item.get('url', '')}",
                    "hot": str(item.get("published_at", "")),
                    "time": datetime.now().strftime("%H:%M")
                })
            return items
        except Exception as e:
            print(f"❌ 36Kr: {e}")
            return []


# 注册爬虫
SPIDERS = {
    "weibo": WeiboSpider,
    "baidu": BaiduSpider,
    "bilibili": BilibiliSpider,
    "douyin": DouyinSpider,
    "zhihu": ZhihuSpider,
    "toutiao": ToutiaoSpider,
    "wallstreetcn": WallstreetcnSpider,
    "thepaper": ThepaperSpider,
    "ifeng": IfengSpider,
    "sspai": SspaiSpider,
    "v2ex": V2exSpider,
    "jin10": Jin10Spider,
    "ithome": IthomeSpider,
    "36kr": Kr36Spider,
}


async def fetch_all_spiders(platforms: List[str] = None) -> dict:
    """获取所有平台的热点"""
    import asyncio
    
    if platforms is None:
        platforms = list(SPIDERS.keys())
    
    results = {}
    
    for platform in platforms:
        if platform not in SPIDERS:
            continue
        
        try:
            spider = SPIDERS[platform]()
            news = await asyncio.to_thread(spider.fetch)
            results[platform] = news
            print(f"✅ {spider.name}: 获取 {len(news)} 条")
        except Exception as e:
            print(f"❌ {platform}: {e}")
            results[platform] = []
    
    return results
