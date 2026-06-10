#!/usr/bin/env python3
"""
爬虫模块 - 扩展版
"""
import logging
import os
import asyncio
import hashlib
import json
import re
import time
import requests
from bs4 import BeautifulSoup
from typing import List
from datetime import datetime, timezone
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


def format_beijing_timestamp(timestamp) -> str:
    if not timestamp:
        return ""
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone().strftime("%H:%M")
    except Exception:
        return ""


def format_rfc822_to_beijing(pub_date: str) -> str:
    if not pub_date:
        return ""
    try:
        dt = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%H:%M")
    except Exception:
        return ""


class BaseSpider:
    """爬虫基类"""
    name = ""
    
    def fetch(self) -> List[dict]:
        raise NotImplementedError


class WeiboSpider(BaseSpider):
    """微博热搜"""
    name = "weibo"
    COOKIE_ENV = "WEIBO_COOKIE"
    BASE_URL = "https://s.weibo.com"
    HOT_URL = f"{BASE_URL}/top/summary?cate=realtimehot"
    
    def fetch(self) -> List[dict]:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Referer": self.HOT_URL,
        }
        cookie = os.getenv(self.COOKIE_ENV) or "SUB=_2AkMWIuNSf8NxqwJRmP8dy2rhaoV2ygrEieKgfhKJJRMxHRl-yT9jqk86tRB6PaLNvQZR6zYUcYVT1zSjoSreQHidcUq7"
        headers["Cookie"] = cookie
        session.headers.update(headers)
        
        try:
            resp = session.get(self.HOT_URL, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            items = []
            for row in soup.select("#pl_top_realtimehot table tbody tr")[1:51]:
                link = next((a for a in row.select("td.td-02 a") if (a.get("href") or "") and "javascript:void(0);" not in (a.get("href") or "")), None)
                if not link:
                    continue
                title = link.get_text(strip=True)
                href = link.get("href", "")
                if not title or not href:
                    continue
                items.append({
                    "platform": "微博",
                    "title": title,
                    "url": f"{self.BASE_URL}{href}",
                    "hot": "",
                    "time": ""
                })
            return items
        except Exception as e:
            logger.exception("❌ 微博")
            return []


class BaiduSpider(BaseSpider):
    """百度热搜"""
    name = "baidu"
    
    def fetch(self) -> List[dict]:
        url = "https://top.baidu.com/board?tab=realtime"
        
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            match = re.search(r'<!--s-data:(.*?)-->', resp.text, re.S)
            if not match:
                return []
            
            data = json.loads(match.group(1))
            items = []
            for item in data.get("data", {}).get("cards", [{}])[0].get("content", []):
                if item.get("isTop"):
                    continue
                # 使用百度搜索页URL
                word = item.get("word", "")
                search_url = f"https://www.baidu.com/s?{urlencode({'wd': word})}"
                # 百度热搜列表没有稳定的原始发布时间字段，使用抓取入库时间由前端按本地时区显示
                items.append({
                    "platform": "百度",
                    "title": word,
                    "url": search_url,
                    "hot": "",
                    "time": ""
                })
            return items
        except Exception as e:
            logger.exception("❌ 百度")
            return []



class BilibiliSpider(BaseSpider):
    """B站热搜"""
    name = "bilibili"
    
    def fetch(self) -> List[dict]:
        url = "https://s.search.bilibili.com/main/hotword?limit=30"
        headers = {"User-Agent": "Mozilla/5.0"}
        
        try:
            resp = requests.get(url, timeout=10, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            items = []
            for item in data.get("list", [])[:30]:
                keyword = item.get("keyword", "")
                title = item.get("show_name") or keyword
                if title and keyword:
                    items.append({
                        "platform": "B站",
                        "title": title,
                        "url": f"https://search.bilibili.com/all?{urlencode({'keyword': keyword})}",
                        "hot": str(item.get("score", "")),
                        "time": ""
                    })
            return items
        except Exception as e:
            logger.exception("❌ B站")
            return []

class BilibiliHotVideoSpider(BaseSpider):
    """B站热门视频"""
    name = "bilibili-hot-video"

    def fetch(self) -> List[dict]:
        url = "https://api.bilibili.com/x/web-interface/popular"
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/"})
            resp.raise_for_status()
            data = resp.json()
            items = []
            for video in data.get("data", {}).get("list", [])[:30]:
                bvid = video.get("bvid", "")
                title = video.get("title", "")
                stat = video.get("stat", {})
                if title and bvid:
                    items.append({
                        "platform": "B站热门视频",
                        "title": title,
                        "url": f"https://www.bilibili.com/video/{bvid}",
                        "hot": f"{stat.get('view', 0)}观看",
                        "time": format_beijing_timestamp(video.get("pubdate")),
                    })
            return items
        except Exception as e:
            logger.exception("❌ B站热门视频")
            return []


class BilibiliRankingSpider(BaseSpider):
    """B站排行榜"""
    name = "bilibili-ranking"

    def fetch(self) -> List[dict]:
        url = "https://api.bilibili.com/x/web-interface/ranking?rid=0&day=3"
        try:
            session = requests.Session()
            session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/v/popular/rank/all"})
            session.get("https://www.bilibili.com/", timeout=10)
            resp = session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            items = []
            for video in data.get("data", {}).get("list", [])[:30]:
                bvid = video.get("bvid", "")
                title = video.get("title", "")
                stat = video.get("stat", {})
                if title and bvid:
                    items.append({
                        "platform": "B站排行榜",
                        "title": title,
                        "url": f"https://www.bilibili.com/video/{bvid}",
                        "hot": f"{stat.get('view', 0)}观看",
                        "time": format_beijing_timestamp(video.get("pubdate")),
                    })
            return items
        except Exception as e:
            logger.exception("❌ B站排行榜")
            return []


class DouyinSpider(BaseSpider):
    """抖音热搜"""
    name = "douyin"
    
    def fetch(self) -> List[dict]:
        url = "https://www.douyin.com/aweme/v1/web/hot/search/list/?device_platform=webapp&aid=6383&channel=channel_pc_web&detail_list=1"
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Referer": "https://www.douyin.com/",
        }

        try:
            session.get("https://login.douyin.com/", timeout=10, headers=headers)
            resp = session.get(url, timeout=10, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            items = []
            for item in data.get("data", {}).get("word_list", [])[:30]:
                title = item.get("word", "")
                sentence_id = item.get("sentence_id", "")
                if title and sentence_id:
                    items.append({
                        "platform": "抖音",
                        "title": title,
                        "url": f"https://www.douyin.com/hot/{sentence_id}",
                        "hot": str(item.get("hot_value", "")),
                        "time": format_beijing_timestamp(item.get("event_time")),
                    })
            return items
        except Exception as e:
            logger.exception("❌ 抖音")
            return []



class ZhihuSpider(BaseSpider):
    """知乎热榜"""
    name = "zhihu"
    
    def fetch(self) -> List[dict]:
        url = "https://www.zhihu.com/api/v3/feed/topstory/hot-list-web?limit=20&desktop=true"
        
        try:
            resp = requests.get(url, timeout=10, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            resp.raise_for_status()
            data = resp.json()
            items = []
            for item in data.get("data", [])[:20]:
                target = item.get("target", {})
                title = target.get("title_area", {}).get("text", "")
                link = target.get("link", {}).get("url", "")
                if title and link:
                    items.append({
                        "platform": "知乎",
                        "title": title,
                        "url": link,
                        "hot": target.get("metrics_area", {}).get("text", ""),
                        "time": ""
                    })
            return items
        except Exception as e:
            logger.exception("❌ 知乎")
            return []


class ToutiaoSpider(BaseSpider):
    """头条热搜"""
    name = "toutiao"
    
    def fetch(self) -> List[dict]:
        url = "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc"
        
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            cookie = os.getenv("TOUTIAO_COOKIE")
            if cookie:
                headers["Cookie"] = cookie
            resp = requests.get(url, timeout=10, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            items = []
            for item in data.get("data", [])[:30]:
                cluster_id = item.get("ClusterIdStr", "")
                title = item.get("Title", "")
                if title and cluster_id:
                    items.append({
                        "platform": "头条",
                        "title": title,
                        "url": f"https://www.toutiao.com/trending/{cluster_id}/",
                        "hot": str(item.get("HotValue", "")),
                        "time": ""
                    })
            return items
        except Exception as e:
            logger.exception("❌ 头条")
            return []

class WallstreetcnSpider(BaseSpider):
    """华尔街见闻"""
    name = "wallstreetcn"
    
    def fetch(self) -> List[dict]:
        url = "https://api-one.wallstcn.com/apiv1/content/lives?channel=global-channel&limit=30"
        
        try:
            resp = requests.get(url, timeout=10, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://wallstreetcn.com/"
            })
            resp.raise_for_status()
            data = resp.json()
            items = []
            for item in data.get("data", {}).get("items", [])[:30]:
                title = item.get("title") or item.get("content_text") or item.get("content_short") or ""
                link = item.get("uri", "")
                if not title or not link:
                    continue
                items.append({
                    "platform": "华尔街见闻",
                    "title": title,
                    "url": link,
                    "hot": "",
                    "time": format_beijing_timestamp(item.get("display_time")),
                })
            return items
        except Exception as e:
            logger.exception("❌ 华尔街见闻")
            return []



class ThepaperSpider(BaseSpider):
    """澎湃新闻"""
    name = "thepaper"
    
    def fetch(self) -> List[dict]:
        url = "https://cache.thepaper.cn/contentapi/wwwIndex/rightSidebar"
        
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            data = resp.json()
            items = []
            for item in data.get("data", {}).get("hotNews", [])[:30]:
                title = item.get("name", "")
                cont_id = item.get("contId", "")
                if title and cont_id:
                    items.append({
                        "platform": "澎湃",
                        "title": title,
                        "url": f"https://www.thepaper.cn/newsDetail_forward_{cont_id}",
                        "hot": "",
                        "time": ""
                    })
            return items
        except Exception as e:
            logger.exception("❌ 澎湃")
            return []

class IfengSpider(BaseSpider):
    """凤凰网 - 使用网页解析"""
    name = "ifeng"
    
    def fetch(self) -> List[dict]:
        url = "https://www.ifeng.com/"
        
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            items = []
            
            # 提取新闻标题和链接
            for item in soup.select("a[title]")[:25]:
                title = item.get("title", "").strip()
                href = item.get("href", "")
                # 过滤有效的新闻链接
                if title and len(title) > 8 and "ifeng.com" in href and "javascript" not in href:
                    items.append({
                        "platform": "凤凰",
                        "title": title,
                        "url": href if href.startswith("http") else f"https://news.ifeng.com{href}",
                        "hot": "",
                        "time": ""
                    })
            
            # 去重
            seen = set()
            unique_items = []
            for item in items:
                if item["title"] not in seen:
                    seen.add(item["title"])
                    unique_items.append(item)
            
            return unique_items[:20]
        except Exception as e:
            logger.exception("❌ 凤凰")
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
            resp.raise_for_status()
            data = resp.json()
            items = []
            for item in data.get("data", []):
                items.append({
                    "platform": "少数派",
                    "title": item.get("title", ""),
                    "url": f"https://sspai.com/post/{item.get('id', '')}",
                    "hot": "",
                    "time": ""
                })
            return items
        except Exception as e:
            logger.exception("❌ 少数派")
            return []



class GitHubSpider(BaseSpider):
    """GitHub Trending"""
    name = "github"
    
    def fetch(self) -> List[dict]:
        url = "https://github.com/trending?spoken_language_code="
        
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            items = []
            for article in soup.select("main .Box div[data-hpc] > article")[:25]:
                link = article.select_one("h2 a")
                if not link:
                    continue
                title = re.sub(r"\s+", "", link.get_text())
                href = link.get("href", "")
                star_link = article.select_one("[href$=stargazers]")
                hot = re.sub(r"\s+", "", star_link.get_text()) if star_link else ""
                if title and href:
                    items.append({
                        "platform": "GitHub",
                        "title": title,
                        "url": f"https://github.com{href}",
                        "hot": hot,
                        "time": ""
                    })
            return items
        except Exception as e:
            logger.exception("❌ GitHub")
            return []

class ClsSpider(BaseSpider):
    """财联社电报"""
    name = "cls"

    def fetch(self) -> List[dict]:
        url = "https://www.cls.cn/v1/roll/get_roll_list"
        params = {
            "appName": "CailianpressWeb",
            "os": "web",
            "refresh_type": "1",
            "rn": "30",
            "sv": "7.7.5",
            "last_time": str(int(time.time())),
        }
        sign_base = urlencode(sorted(params.items()))
        params["sign"] = hashlib.md5(hashlib.sha1(sign_base.encode()).hexdigest().encode()).hexdigest()
        try:
            resp = requests.get(url, params=params, timeout=10, headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.cls.cn/telegraph",
            })
            resp.raise_for_status()
            data = resp.json()
            items = []
            for item in data.get("data", {}).get("roll_data", [])[:30]:
                if item.get("is_ad"):
                    continue
                title = item.get("title") or item.get("brief") or item.get("content", "")
                link = item.get("shareurl") or f"https://www.cls.cn/detail/{item.get('id')}"
                if title and link:
                    items.append({
                        "platform": "财联社",
                        "title": title,
                        "url": link,
                        "hot": "",
                        "time": format_beijing_timestamp(item.get("ctime")),
                    })
            return items[:20]
        except Exception as e:
            logger.exception("❌ 财联社")
            return []


class TencentSpider(BaseSpider):
    """腾讯新闻"""
    name = "tencent"

    def fetch(self) -> List[dict]:
        url = "https://i.news.qq.com/web_backend/v2/getTagInfo?tagId=aEWqxLtdgmQ%3D"
        try:
            resp = requests.get(url, timeout=10, headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://news.qq.com/",
            })
            resp.raise_for_status()
            data = resp.json()
            articles = data.get("data", {}).get("tabs", [{}])[0].get("articleList", [])
            items = []
            for item in articles[:20]:
                link_info = item.get("link_info", {})
                title = item.get("title", "")
                url = link_info.get("url", "")
                if title and url:
                    items.append({
                        "platform": "腾讯新闻",
                        "title": title,
                        "url": url,
                        "hot": "",
                        "time": "",
                    })
            return items
        except Exception as e:
            logger.exception("❌ 腾讯新闻")
            return []


class KaopuSpider(BaseSpider):
    """靠谱新闻"""
    name = "kaopu"

    def fetch(self) -> List[dict]:
        url = "https://kaopustorage.blob.core.windows.net/news-prod/news_list_hans_0.json"
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            data = resp.json()
            items = []
            for item in data[:20]:
                publisher = item.get("publisher", "")
                if publisher in {"财新", "公视"}:
                    continue
                title = item.get("title", "")
                link = item.get("link", "")
                if title and link:
                    items.append({
                        "platform": "靠谱新闻",
                        "title": title,
                        "url": link,
                        "hot": publisher,
                        "time": "",
                    })
            return items
        except Exception as e:
            logger.exception("❌ 靠谱新闻")
            return []


class CankaoXiaoxiSpider(BaseSpider):
    """参考消息"""
    name = "cankaoxiaoxi"

    def fetch(self) -> List[dict]:
        channels = ["zhongguo", "guandian", "gj"]
        items = []
        try:
            for channel in channels:
                url = f"https://china.cankaoxiaoxi.com/json/channel/{channel}/list.json"
                resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"}, verify=False)
                resp.raise_for_status()
                data = resp.json()
                for row in data.get("list", [])[:10]:
                    item = row.get("data", {})
                    title = item.get("title", "")
                    link = item.get("url", "")
                    if title and link:
                        items.append({
                            "platform": "参考消息",
                            "title": title,
                            "url": link,
                            "hot": "",
                            "time": "",
                        })
            return items[:20]
        except Exception as e:
            logger.exception("❌ 参考消息")
            return []


class HupuSpider(BaseSpider):
    """虎扑"""
    name = "hupu"

    def fetch(self) -> List[dict]:
        url = "https://bbs.hupu.com/topic-daily-hot"
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            matches = re.findall(r'<a href="(/[^"]+?\.html)"[^>]*?class="p-title"[^>]*>([^<]+)</a>', resp.text)
            items = []
            for path, title in matches[:20]:
                title = BeautifulSoup(title, "html.parser").get_text(strip=True)
                if title:
                    items.append({
                        "platform": "虎扑",
                        "title": title,
                        "url": f"https://bbs.hupu.com{path}",
                        "hot": "",
                        "time": "",
                    })
            return items
        except Exception as e:
            logger.exception("❌ 虎扑")
            return []


class TiebaSpider(BaseSpider):
    """百度贴吧"""
    name = "tieba"

    def fetch(self) -> List[dict]:
        url = "https://tieba.baidu.com/hottopic/browse/topicList"
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            data = resp.json()
            items = []
            for item in data.get("data", {}).get("bang_topic", {}).get("topic_list", [])[:20]:
                title = item.get("topic_name", "")
                link = item.get("topic_url", "")
                if title and link:
                    items.append({
                        "platform": "百度贴吧",
                        "title": title,
                        "url": link,
                        "hot": "",
                        "time": "",
                    })
            return items
        except Exception as e:
            logger.exception("❌ 百度贴吧")
            return []



class IthomeSpider(BaseSpider):
    """IT之家"""
    name = "ithome"
    
    def fetch(self) -> List[dict]:
        url = "https://www.ithome.com/list/"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        try:
            resp = requests.get(url, timeout=10, headers=headers)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            items = []
            for row in soup.select("#list > div.fl > ul > li")[:30]:
                link = row.select_one("a.t")
                if not link:
                    continue
                title = link.get_text(strip=True)
                href = link.get("href", "")
                if href and title and "lapin" not in href and not any(k in title for k in ["神券", "优惠", "补贴", "京东"]):
                    items.append({
                        "platform": "IT之家",
                        "title": title,
                        "url": href,
                        "hot": "",
                        "time": row.select_one("i").get_text(strip=True) if row.select_one("i") else ""
                    })
            return items
        except Exception as e:
            logger.exception("❌ IT之家")
            return []


class Kr36Spider(BaseSpider):
    """36Kr 快讯"""
    name = "36kr"
    
    def fetch(self) -> List[dict]:
        base_url = "https://www.36kr.com"
        url = f"{base_url}/newsflashes"
        
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            items = []
            for row in soup.select(".newsflash-item")[:30]:
                link = row.select_one("a.item-title")
                if not link:
                    continue
                title = link.get_text(strip=True)
                href = link.get("href", "")
                if title and href:
                    items.append({
                        "platform": "36Kr",
                        "title": title,
                        "url": f"{base_url}{href}" if href.startswith("/") else href,
                        "hot": "",
                        "time": row.select_one(".time").get_text(strip=True) if row.select_one(".time") else ""
                    })
            return items
        except Exception as e:
            logger.exception("❌ 36Kr")
            return []

# 注册爬虫
SPIDERS = {
    "weibo": WeiboSpider,
    "baidu": BaiduSpider,
    "bilibili": BilibiliSpider,
    "bilibili-hot-video": BilibiliHotVideoSpider,
    "bilibili-ranking": BilibiliRankingSpider,
    "douyin": DouyinSpider,
    "zhihu": ZhihuSpider,
    "toutiao": ToutiaoSpider,
    "wallstreetcn": WallstreetcnSpider,
    "thepaper": ThepaperSpider,
    "ifeng": IfengSpider,
    "sspai": SspaiSpider,
    "github": GitHubSpider,
    "cls": ClsSpider,
    "ithome": IthomeSpider,
    "36kr": Kr36Spider,
    "tencent": TencentSpider,
    "kaopu": KaopuSpider,
    "cankaoxiaoxi": CankaoXiaoxiSpider,
    "hupu": HupuSpider,
    "tieba": TiebaSpider,
}


def get_env_number(name: str, default, cast, min_value, max_value):
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = cast(raw)
    except ValueError:
        logger.warning("%s=%r 无效，使用默认值 %s", name, raw, default)
        return default
    if value < min_value or value > max_value:
        logger.warning("%s=%r 超出范围，使用默认值 %s", name, raw, default)
        return default
    return value


SPIDER_CONCURRENCY = get_env_number("SPIDER_CONCURRENCY", 5, int, 1, 20)
SPIDER_FETCH_TIMEOUT_SECONDS = get_env_number("SPIDER_FETCH_TIMEOUT_SECONDS", 15.0, float, 1.0, 60.0)


async def fetch_all_spiders(platforms: List[str] = None) -> dict:
    """获取所有平台的热点"""
    
    if platforms is None:
        platforms = list(SPIDERS.keys())
    
    results = {}
    semaphore = asyncio.Semaphore(max(1, SPIDER_CONCURRENCY))

    async def fetch_one(platform: str):
        if platform not in SPIDERS:
            return None
        async with semaphore:
            try:
                spider = SPIDERS[platform]()
                news = await asyncio.wait_for(
                    asyncio.to_thread(spider.fetch),
                    timeout=max(0.001, SPIDER_FETCH_TIMEOUT_SECONDS),
                )
                logger.info("✅ %s: 获取 %s 条", spider.name, len(news))
                return platform, news
            except Exception:
                logger.exception("❌ %s", platform)
                return platform, []

    fetched = await asyncio.gather(*(fetch_one(platform) for platform in platforms))
    for item in fetched:
        if item is not None:
            platform, news = item
            results[platform] = news
    
    return results
