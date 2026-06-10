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
from urllib.parse import urlencode, urljoin

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


def format_datetime_text(value: str) -> str:
    if not value:
        return ""
    match = re.search(r"(\d{1,2}:\d{2})", value)
    return match.group(1) if match else value.strip()


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
                href = str(link.get("href") or "")
                if not title or not href:
                    continue
                items.append({
                    "platform": "微博热搜",
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
    """凤凰网"""
    name = "ifeng"

    def _parse_links_fallback(self, html: str) -> List[dict]:
        soup = BeautifulSoup(html, "html.parser")
        items = []
        seen = set()
        for link in soup.select('a[href*="ifeng.com/c/"], a[href*="news.ifeng.com/"]'):
            title = str(link.get("title") or link.get_text(" ", strip=True)).strip()
            href = str(link.get("href", "")).strip()
            if not title or not href or title in seen:
                continue
            seen.add(title)
            items.append({
                "platform": "凤凰",
                "title": title,
                "url": href,
                "hot": "",
                "time": ""
            })
            if len(items) >= 20:
                break
        return items
    
    def fetch(self) -> List[dict]:
        url = "https://www.ifeng.com/"
        
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            match = re.search(r"var\s+allData\s*=\s*(\{[\s\S]*?\});", resp.text)
            items = []
            if match:
                data = json.loads(match.group(1))
                for item in data.get("hotNews1", []):
                    title = item.get("title", "").strip()
                    href = item.get("url", "")
                    if not title or not href:
                        continue
                    items.append({
                        "platform": "凤凰",
                        "title": title,
                        "url": href,
                        "hot": "",
                        "time": item.get("newsTime", "")
                    })
            if items:
                return items[:20]
            logger.warning(
                "⚠️ 凤凰 hotNews1 为空，使用链接兜底: status=%s html_len=%s has_allData=%s matched=%s",
                resp.status_code,
                len(resp.text),
                "allData" in resp.text,
                bool(match),
            )
            return self._parse_links_fallback(resp.text)
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
                href = str(link.get("href") or "")
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


class Jin10Spider(BaseSpider):
    """金十数据"""
    name = "jin10"

    def fetch(self) -> List[dict]:
        url = f"https://www.jin10.com/flash_newest.js?t={int(time.time() * 1000)}"
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.jin10.com/"})
            resp.raise_for_status()
            text = re.sub(r"^\s*var\s+newest\s*=\s*", "", resp.text).strip().rstrip(";")
            data = json.loads(text)
            items = []
            for item in data[:30]:
                if 5 in (item.get("channel") or []):
                    continue
                detail = item.get("data") or {}
                raw_title = detail.get("title") or detail.get("content") or ""
                title = re.sub(r"</?b>", "", raw_title).strip()
                match = re.match(r"^【([^】]+)】(.*)$", title)
                if match:
                    title = match.group(1)
                if title and item.get("id"):
                    items.append({
                        "platform": "金十数据",
                        "title": title,
                        "url": f"https://flash.jin10.com/detail/{item.get('id')}",
                        "hot": "✰" if item.get("important") else "",
                        "time": format_datetime_text(item.get("time", "")),
                    })
            return items
        except Exception:
            logger.exception("❌ 金十数据")
            return []


class ZaobaoSpider(BaseSpider):
    """联合早报"""
    name = "zaobao"

    def fetch(self) -> List[dict]:
        base_url = "https://www.zaochenbao.com"
        try:
            resp = requests.get(f"{base_url}/realtime/", timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            html = resp.content.decode("gb2312", errors="ignore")
            soup = BeautifulSoup(html, "html.parser")
            items = []
            for row in soup.select("div.list-block > a.item")[:30]:
                title_el = row.select_one(".eps")
                time_el = row.select_one(".pdt10")
                href = str(row.get("href", ""))
                title = title_el.get_text(strip=True) if title_el else ""
                if title and href:
                    items.append({
                        "platform": "联合早报",
                        "title": title,
                        "url": urljoin(base_url, href),
                        "hot": "",
                        "time": format_datetime_text(time_el.get_text(" ", strip=True) if time_el else ""),
                    })
            return items
        except Exception:
            logger.exception("❌ 联合早报")
            return []


class GelonghuiSpider(BaseSpider):
    """格隆汇"""
    name = "gelonghui"

    def fetch(self) -> List[dict]:
        base_url = "https://www.gelonghui.com"
        try:
            resp = requests.get(f"{base_url}/news/", timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            items = []
            for row in soup.select(".article-content")[:30]:
                link = row.select_one(".detail-right > a")
                title_el = link.select_one("h2") if link else None
                time_el = row.select_one(".time > span:nth-child(3)")
                href = str(link.get("href", "")) if link else ""
                title = title_el.get_text(strip=True) if title_el else ""
                if title and href:
                    items.append({
                        "platform": "格隆汇",
                        "title": title,
                        "url": urljoin(base_url, href),
                        "hot": "",
                        "time": format_datetime_text(time_el.get_text(" ", strip=True) if time_el else ""),
                    })
            return items
        except Exception:
            logger.exception("❌ 格隆汇")
            return []


class FastbullSpider(BaseSpider):
    """法布财经"""
    name = "fastbull"

    def fetch(self) -> List[dict]:
        url = "https://api.fastbull.com/fastbull-news-service/api/getNewsPageOrderByTimeDesc"
        payload = {"pageSize": 30, "reqSource": 0, "showPoint": 1, "showNewsTypeList": [1, 2, 5]}
        try:
            resp = requests.post(url, json=payload, timeout=10, headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.fastbull.com/cn/express-news",
                "Origin": "https://www.fastbull.com",
            })
            resp.raise_for_status()
            body = json.loads(resp.json().get("bodyMessage", "{}"))
            items = []
            for item in body.get("pageDatas", [])[:30]:
                title = item.get("translateTitle") or item.get("title") or ""
                path = item.get("path") or item.get("newsId") or ""
                if title and path:
                    items.append({
                        "platform": "法布财经",
                        "title": title,
                        "url": f"https://www.fastbull.com/cn/news-detail/{path}",
                        "hot": str(item.get("point") or ""),
                        "time": format_beijing_timestamp((item.get("pubTime") or 0) / 1000),
                    })
            return items
        except Exception:
            logger.exception("❌ 法布财经")
            return []


class PcbetaSpider(BaseSpider):
    """远景论坛 Win11"""
    name = "pcbeta"

    def fetch(self) -> List[dict]:
        try:
            resp = requests.get("https://bbs.pcbeta.com/forum.php?mod=rss&fid=563&auth=0", timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "xml")
            items = []
            for row in soup.select("item")[:30]:
                title = row.title.get_text(strip=True) if row.title else ""
                link = row.link.get_text(strip=True) if row.link else ""
                pub_date = row.pubDate.get_text(strip=True) if row.pubDate else ""
                if title and link:
                    items.append({
                        "platform": "远景论坛",
                        "title": title,
                        "url": link,
                        "hot": "",
                        "time": format_rfc822_to_beijing(pub_date),
                    })
            return items
        except Exception:
            logger.exception("❌ 远景论坛")
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
                href = str(link.get("href") or "")
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
                href = str(link.get("href") or "")
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


class Kr36RenqiSpider(BaseSpider):
    """36氪人气榜"""
    name = "36kr-renqi"

    def fetch(self) -> List[dict]:
        url = "https://gateway.36kr.com/api/mis/nav/home/nav/rank/hot"
        try:
            resp = requests.post(
                url,
                timeout=10,
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
                json={"partner_id": "web", "param": {"siteId": 1, "platformId": 2}},
            )
            resp.raise_for_status()
            data = resp.json()
            items = []
            for row in data.get("data", {}).get("hotRankList", [])[:30]:
                item_id = row.get("itemId")
                material = row.get("templateMaterial", {})
                title = material.get("widgetTitle", "")
                if item_id and title:
                    items.append({
                        "platform": "36氪人气榜",
                        "title": title,
                        "url": f"https://36kr.com/p/{item_id}",
                        "hot": "  |  ".join(v for v in [material.get("authorName", ""), material.get("statFormat", "")] if v),
                        "time": "",
                    })
            return items
        except Exception:
            logger.exception("❌ 36氪人气榜")
            return []


class XueqiuHotstockSpider(BaseSpider):
    """雪球热门股票"""
    name = "xueqiu-hotstock"

    def fetch(self) -> List[dict]:
        url = "https://stock.xueqiu.com/v5/stock/hot_stock/list.json?size=30&_type=10&type=10"
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://xueqiu.com/hq"}
        try:
            session = requests.Session()
            session.headers.update(headers)
            session.get("https://xueqiu.com/hq", timeout=10).raise_for_status()
            resp = session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            items = []
            for row in data.get("data", {}).get("items", [])[:30]:
                if row.get("ad"):
                    continue
                code = row.get("code", "")
                title = row.get("name", "")
                if code and title:
                    percent = row.get("percent", "")
                    exchange = row.get("exchange", "")
                    items.append({
                        "platform": "雪球热门股票",
                        "title": title,
                        "url": f"https://xueqiu.com/s/{code}",
                        "hot": f"{percent}% {exchange}".strip(),
                        "time": "",
                    })
            return items
        except Exception:
            logger.exception("❌ 雪球热门股票")
            return []


class KuaishouSpider(BaseSpider):
    """快手热榜"""
    name = "kuaishou"

    def fetch(self) -> List[dict]:
        url = "https://www.kuaishou.com/?isHome=1"
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            match = re.search(r"window\.__APOLLO_STATE__\s*=\s*(\{.+?\});", resp.text)
            if not match:
                return []
            data = json.loads(match.group(1))
            root = data.get("defaultClient", {}).get("ROOT_QUERY", {})
            hot_rank_id = root.get('visionHotRank({"page":"home"})', {}).get("id")
            hot_rank = data.get("defaultClient", {}).get(hot_rank_id, {}) if hot_rank_id else {}
            items = []
            for item in hot_rank.get("items", [])[:30]:
                item_id = item.get("id", "")
                row = data.get("defaultClient", {}).get(item_id, {})
                if row.get("tagType") == "置顶":
                    continue
                title = row.get("name", "")
                if title:
                    items.append({
                        "platform": "快手",
                        "title": title,
                        "url": f"https://www.kuaishou.com/search/video?{urlencode({'searchKey': title})}",
                        "hot": "",
                        "time": "",
                    })
            return items
        except Exception:
            logger.exception("❌ 快手")
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
    "jin10": Jin10Spider,
    "zaobao": ZaobaoSpider,
    "gelonghui": GelonghuiSpider,
    "fastbull": FastbullSpider,
    "pcbeta": PcbetaSpider,
    "ithome": IthomeSpider,
    "36kr": Kr36Spider,
    "36kr-renqi": Kr36RenqiSpider,
    "xueqiu-hotstock": XueqiuHotstockSpider,
    "kuaishou": KuaishouSpider,
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
