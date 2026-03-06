#!/usr/bin/env python3
"""
热点资讯爬虫框架
参考 newsnow 项目: https://github.com/ourongxing/newsnow
"""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ========== 数据模型 ==========

@dataclass
class NewsItem:
    """新闻条目"""
    id: str
    title: str
    url: str
    mobile_url: Optional[str] = None
    pub_date: Optional[str] = None
    hot_value: Optional[str] = None  # 热度值
    extra: dict = field(default_factory=dict)


@dataclass
class SourceConfig:
    """数据源配置"""
    name: str
    interval: int = 300000  # 刷新间隔（毫秒）
    color: str = "blue"
    column: str = "default"
    home: str = ""
    title: str = ""


# ========== 爬虫基类 ==========

class BaseSource(ABC):
    """爬虫基类"""
    
    config: SourceConfig
    
    def __init__(self):
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """创建带重试的 session"""
        session = requests.Session()
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        return session
    
    async def fetch(self) -> list[NewsItem]:
        """获取热点数据"""
        return await asyncio.to_thread(self._fetch)
    
    @abstractmethod
    def _fetch(self) -> list[NewsItem]:
        """实际抓取逻辑（同步）"""
        pass
    
    @property
    def source_name(self) -> str:
        return self.config.name


# ========== 微博热搜 ==========

class WeiboSource(BaseSource):
    """微博热搜爬虫"""
    
    config = SourceConfig(
        name="微博",
        interval=120000,
        color="red",
        column="social",
        home="https://weibo.com",
        title="实时热搜"
    )
    
    # 备用 Cookie
    COOKIE = "SUB=_2AkMWIuNSf8NxqwJRmP8dy2rhaoV2ygrEieKgfhKJJRMxHRl-yT9jqk86tRB6PaLNvQZR6zYUcYVT1zSjoSreQHidcUq7"
    
    def _create_session(self) -> requests.Session:
        """创建带重试的 session"""
        session = super()._create_session()
        session.headers.update({"Cookie": self.COOKIE})
        return session
    
    def _fetch(self) -> list[NewsItem]:
        url = "https://s.weibo.com/top/summary?cate=realtimehot"
        
        response = self.session.get(url, timeout=10)
        response.raise_for_status()
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        rows = soup.select("#pl_top_realtimehot table tbody tr")
        items = []
        for row in rows[1:]:  # 跳过表头
            try:
                link_elem = row.select_one("td.td-02 a")
                if not link_elem:
                    continue
                
                href = link_elem.get("href", "")
                if not href or "javascript" in href:
                    continue
                
                title = link_elem.get_text(strip=True)
                if not title:
                    continue
                
                # 获取热度标识
                flag_elem = row.select_one("td.td-03")
                flag = flag_elem.get_text(strip=True) if flag_elem else ""
                icon_map = {"新": "🆕", "热": "🔥", "爆": "💥"}
                
                items.append(NewsItem(
                    id=title,
                    title=title,
                    url=f"https://s.weibo.com{href}",
                    mobile_url=f"https://m.weibo.cn/detail/raw?id={title}",
                    extra={"flag": icon_map.get(flag, "")}
                ))
            except Exception:
                continue
        
        return items


# ========== 抖音热搜 ==========

class DouyinSource(BaseSource):
    """抖音热搜爬虫"""
    
    config = SourceConfig(
        name="抖音",
        interval=120000,
        color="blue",
        column="video",
        home="https://www.douyin.com",
        title="热点榜"
    )
    
    def _fetch(self) -> list[NewsItem]:
        url = "https://www.douyin.com/aweme/v1/web/hot/search/list/?device_platform=webapp&aid=6383&channel=channel_pc_web"
        
        response = self.session.get(url, timeout=10)
        data = response.json()
        
        items = []
        for item in data.get("data", {}).get("word_list", []):
            items.append(NewsItem(
                id=item.get("sentence_id", ""),
                title=item.get("word", ""),
                url=f"https://www.douyin.com/hot/{item.get('sentence_id', '')}",
                hot_value=item.get("hot_value", "")
            ))
        
        return items


# ========== 百度热搜 ==========

class BaiduSource(BaseSource):
    """百度热搜爬虫"""
    
    config = SourceConfig(
        name="百度",
        interval=180000,
        color="blue",
        column="search",
        home="https://www.baidu.com",
        title="实时热搜"
    )
    
    def _fetch(self) -> list[NewsItem]:
        url = "https://top.baidu.com/board?tab=realtime"
        
        response = self.session.get(url, timeout=10)
        
        # 从 HTML 中提取 JSON 数据
        import re
        match = re.search(r'<!--s-data:(.*?)-->', response.text, re.S)
        if not match:
            return []
        
        data = json.loads(match.group(1))
        
        items = []
        for item in data.get("data", {}).get("cards", [{}])[0].get("content", []):
            if item.get("isTop"):
                continue
            items.append(NewsItem(
                id=item.get("rawUrl", ""),
                title=item.get("word", ""),
                url=item.get("rawUrl", ""),
                extra={"desc": item.get("desc", "")}
            ))
        
        return items


# ========== 知乎热搜 ==========

class ZhihuSource(BaseSource):
    """知乎热搜爬虫"""
    
    config = SourceConfig(
        name="知乎",
        interval=300000,
        color="blue",
        column="tech",
        home="https://www.zhihu.com",
        title="热榜"
    )
    
    def _fetch(self) -> list[NewsItem]:
        url = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=50&desktop=true"
        
        response = self.session.get(url, timeout=10)
        data = response.json()
        
        items = []
        for item in data.get("data", []):
            target = item.get("target", {})
            items.append(NewsItem(
                id=str(target.get("id", "")),
                title=target.get("title_area", {}).get("text", ""),
                url=f"https://www.zhihu.com/question/{target.get('id', '')}",
                hot_value=str(item.get("detail_text", ""))
            ))
        
        return items


# ========== B站热搜 ==========

class BilibiliSource(BaseSource):
    """B站热搜爬虫"""
    
    config = SourceConfig(
        name="B站",
        interval=180000,
        color="pink",
        column="video",
        home="https://www.bilibili.com",
        title="热门"
    )
    
    def _fetch(self) -> list[NewsItem]:
        url = "https://api.bilibili.com/x/web-interface/popular"
        
        response = self.session.get(url, timeout=10)
        data = response.json()
        
        items = []
        for item in data.get("data", {}).get("list", []):
            items.append(NewsItem(
                id=str(item.get("aid", "")),
                title=item.get("title", ""),
                url=f"https://www.bilibili.com/video/{item.get('bvid', '')}",
                hot_value=str(item.get("play", 0))
            ))
        
        return items


# ========== 头条热搜 ==========

class ToutiaoSource(BaseSource):
    """头条热搜爬虫"""
    
    config = SourceConfig(
        name="头条",
        interval=180000,
        color="red",
        column="news",
        home="https://www.toutiao.com",
        title="热点"
    )
    
    def _fetch(self) -> list[NewsItem]:
        url = "https://www.toutiao.com/api/pc/feed/?category=news_hot&max_behot_time=0"
        
        response = self.session.get(url, timeout=10)
        data = response.json()
        
        items = []
        for item in data.get("data", []):
            if item.get("media_name"):
                items.append(NewsItem(
                    id=str(item.get("item_id", "")),
                    title=item.get("title", ""),
                    url=f"https://www.toutiao.com{a}",
                    hot_value=str(item.get("read_count", ""))
                ))
        
        return items


# ========== 贴吧热搜 ==========

class TiebaSource(BaseSource):
    """贴吧热搜爬虫"""
    
    config = SourceConfig(
        name="贴吧",
        interval=300000,
        color="blue",
        column="forum",
        home="https://tieba.baidu.com",
        title="热门话题"
    )
    
    def _fetch(self) -> list[NewsItem]:
        url = "https://tieba.baidu.com/hottopic/browse/hottopic?topic_id=&word=&pn=0"
        
        response = self.session.get(url, timeout=10)
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        items = []
        topics = soup.select(".topic-list .item")
        
        for topic in topics:
            try:
                link = topic.select_one("a")
                if not link:
                    continue
                
                title = link.get_text(strip=True)
                href = link.get("href", "")
                
                if title and href:
                    items.append(NewsItem(
                        id=title,
                        title=title,
                        url=f"https://tieba.baidu.com{href}"
                    ))
            except Exception:
                continue
        
        return items


# ========== IT之家 ==========

class IthomeSource(BaseSource):
    """IT之家热搜爬虫"""
    
    config = SourceConfig(
        name="IT之家",
        interval=300000,
        color="orange",
        column="tech",
        home="https://www.ithome.com",
        title="热门"
    )
    
    def _fetch(self) -> list[NewsItem]:
        url = "https://www.ithome.com/ Ranking"
        
        response = self.session.get(url, timeout=10)
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        items = []
        # IT之家结构可能需要根据实际页面调整
        posts = soup.select(".item-post")
        
        for post in posts:
            try:
                link = post.select_one("a")
                if not link:
                    continue
                
                title = link.get_text(strip=True)
                href = link.get("href", "")
                
                if title and href:
                    items.append(NewsItem(
                        id=title,
                        title=title,
                        url=href if href.startswith("http") else f"https://www.ithome.com{href}"
                    ))
            except Exception:
                continue
        
        return items


# ========== 36Kr ==========

class Kr36Source(BaseSource):
    """36Kr热搜爬虫"""
    
    config = SourceConfig(
        name="36Kr",
        interval=300000,
        color="orange",
        column="tech",
        home="https://36kr.com",
        title="热门"
    )
    
    def _fetch(self) -> list[NewsItem]:
        url = "https://36kr.com/pp/api/pc/feed"
        
        response = self.session.get(url, timeout=10)
        data = response.json()
        
        items = []
        for item in data.get("data", {}).get("items", []):
            items.append(NewsItem(
                id=str(item.get("item_id", "")),
                title=item.get("title", ""),
                url=f"https://36kr.com{item.get('url', '')}",
                pub_date=item.get("published_at", "")
            ))
        
        return items


# ========== 数据源注册表 ==========

SOURCES = {
    "weibo": WeiboSource,
    "douyin": DouyinSource,
    "baidu": BaiduSource,
    "zhihu": ZhihuSource,
    "bilibili": BilibiliSource,
    "toutiao": ToutiaoSource,
    "tieba": TiebaSource,
    "ithome": IthomeSource,
    "36kr": Kr36Source,
}


# ========== 主程序 ==========

async def fetch_all_sources(source_names: list[str] = None) -> dict[str, list[NewsItem]]:
    """获取所有指定数据源的热点"""
    if source_names is None:
        source_names = list(SOURCES.keys())
    
    results = {}
    
    for name in source_names:
        if name not in SOURCES:
            print(f"⚠️ 未知数据源: {name}")
            continue
        
        try:
            source = SOURCES[name]()
            items = await source.fetch()
            results[name] = items
            print(f"✅ {source.source_name}: 获取 {len(items)} 条热点")
        except Exception as e:
            print(f"❌ {name}: {str(e)}")
            results[name] = []
    
    return results


async def fetch_with_cache(source_names: list[str] = None, cache_file: str = "cache.json") -> dict[str, list[NewsItem]]:
    """带缓存的获取（如果缓存有效则直接读取）"""
    import os
    
    # 尝试读取缓存
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            cache_time = cache_data.get("timestamp", 0)
            # 5分钟内使用缓存
            if time.time() - cache_time < 300:
                print("📦 使用缓存数据")
                return {k: [NewsItem(**item) for item in v] for k, v in cache_data.get("news", {}).items()}
        except Exception:
            pass
    
    # 抓取新数据
    results = await fetch_all_sources(source_names)
    
    # 保存缓存
    try:
        cache_data = {
            "timestamp": time.time(),
            "news": {k: [asdict(item) for item in v] for k, v in results.items()}
        }
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    
    return results


def format_output(results: dict[str, list[NewsItem]], platform: str = None) -> str:
    """格式化输出"""
    lines = []
    
    if platform:
        # 只输出指定平台
        if platform in results:
            lines.append(f"# {platform.upper()} 热点榜")
            lines.append("")
            for i, item in enumerate(results[platform][:], 1):
                hot = f" (🔥{item.hot_value})" if item.hot_value else ""
                lines.append(f"{i}. {item.title}{hot}")
    else:
        # 输出所有平台
        for source_name, items in results.items():
            if not items:
                continue
            lines.append(f"# {source_name.upper()} 热点榜")
            lines.append("")
            for i, item in enumerate(items[:10], 1):
                hot = f" (🔥{item.hot_value})" if item.hot_value else ""
                lines.append(f"{i}. {item.title}{hot}")
            lines.append("")
    
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="热点资讯爬虫")
    parser.add_argument("-s", "--sources", nargs="+", help="指定数据源，如: weibo douyin baidu")
    parser.add_argument("-p", "--platform", help="只输出指定平台")
    parser.add_argument("-c", "--cache", action="store_true", help="使用缓存")
    parser.add_argument("-o", "--output", help="输出文件")
    
    args = parser.parse_args()
    
    if args.cache:
        results = asyncio.run(fetch_with_cache(args.sources))
    else:
        results = asyncio.run(fetch_all_sources(args.sources))
    
    output = format_output(results, args.platform)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"📝 已保存到 {args.output}")
    else:
        print(output)
