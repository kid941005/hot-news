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
                # 使用百度热搜详情页URL
                hot_id = item.get("hotScore", "")
                word = item.get("word", "")
                # 生成百度搜索URL（改为直接搜索该关键词）
                search_url = f"https://www.baidu.com/s?wd={word}"
                items.append({
                    "platform": "百度",
                    "title": word,
                    "url": search_url,
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
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        try:
            resp = requests.get(url, timeout=10, headers=headers)
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
                # 转换知乎API URL为网页URL
                zhihu_url = target.get("url", "")
                if "/questions/" in zhihu_url:
                    # API: https://api.zhihu.com/questions/123456 -> 网页: https://www.zhihu.com/question/123456
                    question_id = zhihu_url.split("/questions/")[-1].split("?")[0]
                    web_url = f"https://www.zhihu.com/question/{question_id}"
                else:
                    web_url = zhihu_url
                
                # 获取文章实际发布时间
                created = target.get("created")
                if created:
                    pub_time = datetime.fromtimestamp(created).strftime("%H:%M")
                else:
                    pub_time = datetime.now().strftime("%H:%M")
                
                items.append({
                    "platform": "知乎",
                    "title": target.get("title", ""),
                    "url": web_url,
                    "hot": str(item.get("detail_text", "")),
                    "time": pub_time
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
            resp = requests.get(url, timeout=10, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Cookie": "tt_webid=1234567890123456789"
            })
            data = resp.json()
            items = []
            for item in data.get("data", []):
                if item.get("title"):
                    # 获取文章URL
                    article_url = item.get("source_url", "")
                    if article_url and not article_url.startswith("http"):
                        article_url = "https://www.toutiao.com" + article_url
                    
                    # 获取文章发布时间
                    behot_time = item.get("behot_time", 0)
                    if behot_time:
                        pub_time = datetime.fromtimestamp(behot_time).strftime("%H:%M")
                    else:
                        pub_time = datetime.now().strftime("%H:%M")
                    
                    items.append({
                        "platform": "头条",
                        "title": item.get("title", ""),
                        "url": article_url,
                        "hot": str(item.get("read_count", "")),
                        "time": pub_time
                    })
            return items[:30]
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
        url = "https://www.thepaper.cn/xwzl_ghot"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        try:
            resp = requests.get(url, timeout=10, headers=headers)
            data = resp.json()
            items = []
            for item in data.get("data", [])[:30]:
                items.append({
                    "platform": "澎湃",
                    "title": item.get("title", ""),
                    "url": f"https://www.thepaper.cn/news{item.get('id', '')}",
                    "hot": "",
                    "time": item.get("pubTime", "")[:5] if item.get("pubTime") else datetime.now().strftime("%H:%M")
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
        # 使用少数派热门文章API（参考newsnow）
        import time
        timestamp = int(time.time() * 1000)
        url = f"https://sspai.com/api/v1/article/tag/page/get?limit=20&offset=0&created_at={timestamp}&tag=%E7%83%AD%E9%97%A8%E6%96%87%E7%AB%A0&released=false"
        
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            items = []
            for item in data.get("data", []):
                items.append({
                    "platform": "少数派",
                    "title": item.get("title", ""),
                    "url": f"https://sspai.com/post/{item.get('id', '')}",
                    "hot": "",
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
        # 使用RSS feed获取数据（参考newsnow）
        tabs = ["create", "ideas", "programmer", "share"]
        items = []
        
        try:
            for tab in tabs:
                url = f"https://www.v2ex.com/feed/{tab}.json"
                resp = requests.get(url, timeout=10)
                data = resp.json()
                for item in data.get("items", [])[:15]:
                    items.append({
                        "platform": "V2EX",
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "hot": "",
                        "time": datetime.now().strftime("%H:%M")
                    })
            
            # 去重并返回
            seen = set()
            unique_items = []
            for item in items:
                if item["title"] not in seen:
                    seen.add(item["title"])
                    unique_items.append(item)
            
            return unique_items[:30]
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
        import xml.etree.ElementTree as ET
        
        url = "https://www.ithome.com/rss"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        try:
            resp = requests.get(url, timeout=10, headers=headers)
            resp.encoding = 'utf-8'
            
            # 解析RSS
            root = ET.fromstring(resp.text)
            items = root.findall('.//item')
            
            results = []
            for item in items[:20]:
                title = item.find('title').text if item.find('title') is not None else ''
                link = item.find('link').text if item.find('link') is not None else ''
                pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ''
                
                # 解析时间
                if pub_date:
                    # 格式: Sat, 07 Mar 2026 12:47:36 GMT
                    try:
                        dt = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %Z")
                        pub_time = dt.strftime("%H:%M")
                    except:
                        pub_time = datetime.now().strftime("%H:%M")
                else:
                    pub_time = datetime.now().strftime("%H:%M")
                
                if title and link:
                    results.append({
                        "platform": "IT之家",
                        "title": title,
                        "url": link,
                        "hot": "",
                        "time": pub_time
                    })
            
            return results
        except Exception as e:
            print(f"❌ IT之家: {e}")
            return []


class Kr36Spider(BaseSpider):
    """36Kr"""
    name = "36kr"
    
    def fetch(self) -> List[dict]:
        url = "https://36kr.com/pp/api/pc/feed"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://36kr.com/"
        }
        
        try:
            resp = requests.get(url, timeout=10, headers=headers)
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
