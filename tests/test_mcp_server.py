import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.mcp_server import get_latest_news, get_news_by_platform, list_platforms, search_news


class DummyNews:
    id = 1
    platform = "微博热搜"
    title = "测试新闻"
    url = "https://example.com/news"
    hot_value = "100"
    pub_time = "10:00"
    created_at = None

    def to_dict(self):
        return {
            "id": self.id,
            "platform": self.platform,
            "title": self.title,
            "url": self.url,
            "hot_value": self.hot_value,
            "pub_time": self.pub_time,
            "created_at": None,
        }


class DummyQuery:
    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def all(self):
        return [DummyNews()]


class DummyDB:
    def __init__(self):
        self.closed = False

    def query(self, model):
        return DummyQuery()

    def close(self):
        self.closed = True


def test_mcp_list_platforms():
    platforms = list_platforms()
    assert {"id": "weibo", "name": "微博热搜"} in platforms


def test_mcp_get_latest_news_closes_db():
    db = DummyDB()
    with patch("backend.mcp_server.SessionLocal", return_value=db):
        news = get_latest_news("weibo", 1)
    assert news[0]["platform"] == "微博热搜"
    assert db.closed is True


def test_mcp_search_news():
    db = DummyDB()
    with patch("backend.mcp_server.SessionLocal", return_value=db):
        news = search_news("测试", limit=1)
    assert news[0]["title"] == "测试新闻"
    assert db.closed is True


def test_mcp_get_news_by_platform():
    db = DummyDB()
    with patch("backend.mcp_server.SessionLocal", return_value=db):
        grouped = get_news_by_platform(1)
    assert "微博热搜" in grouped
    assert grouped["微博热搜"][0]["title"] == "测试新闻"
    assert db.closed is True
