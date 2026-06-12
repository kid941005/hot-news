import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api import main
from backend.api.main import app, get_current_user_id, get_db
from backend.models.models import UserConfig


class DummyConfigQuery:
    def __init__(self, config):
        self.config = config

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.config


class DummyDB:
    def __init__(self, config):
        self.config = config

    def query(self, model):
        if model is UserConfig or getattr(model, "__name__", "") == "UserConfig":
            return DummyConfigQuery(self.config)
        raise AssertionError(f"unexpected query: {model}")


class DummyNews:
    def __init__(self, news_id, title, created_at):
        self.id = news_id
        self.title = title
        self.platform = "微博热搜"
        self.url = f"https://example.com/{news_id}"
        self.hot_value = ""
        self.pub_time = ""
        self.created_at = created_at

    def to_dict(self):
        return {
            "id": self.id,
            "platform": self.platform,
            "title": self.title,
            "url": self.url,
            "hot_value": self.hot_value,
            "pub_time": self.pub_time,
            "created_at": self.created_at.isoformat() + "Z",
        }


def test_keyword_tag_filters_to_today_news():
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    config = SimpleNamespace(keyword_tags={"AI": ["AI"]}, platforms=[])
    db = DummyDB(config)
    news_list = [
        DummyNews(1, "AI 今日新闻", today),
        DummyNews(2, "AI 旧新闻", yesterday),
    ]
    matched = {1: ["AI"], 2: ["AI"]}

    def override_get_db():
        yield db

    old_last = main.LAST_REFRESH_TIME
    old_running = main._auto_refresh_running
    main.LAST_REFRESH_TIME = datetime.now()
    main._auto_refresh_running = False
    app.dependency_overrides[get_current_user_id] = lambda: 1
    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("backend.api.main._trigger_auto_refresh_if_needed"), \
             patch("backend.api.main._get_refresh_state", return_value={"stale": False, "refreshing": False}), \
             patch("backend.db.database.get_user_filtered_news", return_value=(news_list, matched)):
            response = TestClient(app).get("/api/news?tag=AI")
    finally:
        main.LAST_REFRESH_TIME = old_last
        main._auto_refresh_running = old_running
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert [item["title"] for item in data["news"]] == ["AI 今日新闻"]
    assert [item["title"] for item in data["keyword_groups"]["AI"]] == ["AI 今日新闻"]
