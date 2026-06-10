import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api import main as api
from backend.db.database import CacheRecord
from backend.models.models import News


async def fake_fetch_all_spiders(platforms=None):
    return {"weibo": [{"title": "测试"}]}


class DummyQuery:
    def __init__(self, item=None, items=None):
        self.item = item
        self.items = items
        self.platform = None

    def first(self):
        if self.items is None:
            return self.item
        for item in reversed(self.items):
            if self.platform is None or item.platform == self.platform:
                return item
        return None

    def filter(self, *args, **_kwargs):
        for arg in args:
            right = getattr(arg, "right", None)
            value = getattr(right, "value", None)
            if value:
                self.platform = value
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def delete(self):
        return None


class DummyDB:
    def __init__(self, has_news):
        self.has_news = has_news
        self.cache_records = []
        self.news = []

    def query(self, model):
        if model is News:
            return DummyQuery(object() if self.has_news else None)
        if model is CacheRecord:
            return DummyQuery(items=self.cache_records)
        raise AssertionError(model)

    def add(self, item):
        if isinstance(item, CacheRecord):
            self.cache_records.append(item)
        else:
            self.news.append(item)

    def commit(self):
        pass

    def rollback(self):
        pass


def reset_auto_refresh_state():
    api.LAST_REFRESH_TIME = None
    api._auto_refresh_running = False
    api._auto_refresh_platforms.clear()


def test_auto_refresh_syncs_when_database_is_empty():
    reset_auto_refresh_state()
    calls = []

    with patch.object(api.spiders, "fetch_all_spiders", side_effect=fake_fetch_all_spiders), \
         patch.object(api, "refresh_news_data", side_effect=lambda db, results: calls.append((db, results)) or (1, {})):
        db = DummyDB(has_news=False)
        api._trigger_auto_refresh_if_needed(db)

    assert calls == [(db, {"weibo": [{"title": "测试"}]})]
    assert api.LAST_REFRESH_TIME is not None
    assert api._auto_refresh_running is False


def test_auto_refresh_syncs_only_requested_platform_when_database_is_empty():
    reset_auto_refresh_state()
    calls = []

    async def fake_fetch(platforms=None):
        calls.append(platforms)
        return {"weibo": [{"title": "测试"}]}

    with patch.object(api.spiders, "fetch_all_spiders", side_effect=fake_fetch), \
         patch.object(api, "refresh_news_data", return_value=(1, {})):
        api._trigger_auto_refresh_if_needed(DummyDB(has_news=False), ["weibo"])

    assert calls == [["weibo"]]


def test_auto_refresh_skips_during_cooldown():
    reset_auto_refresh_state()
    db = DummyDB(has_news=True)
    db.cache_records.append(type("CacheRecord", (), {
        "platform": "weibo",
        "last_fetch": datetime.now(timezone.utc),
        "last_success_at": datetime.now(timezone.utc),
    })())

    with patch("threading.Thread") as thread:
        api._trigger_auto_refresh_if_needed(db, ["weibo"])

    thread.assert_not_called()
    assert api._auto_refresh_running is False


def test_auto_refresh_starts_background_thread_when_data_is_stale():
    reset_auto_refresh_state()
    db = DummyDB(has_news=True)
    db.cache_records.append(type("CacheRecord", (), {
        "platform": "weibo",
        "last_fetch": datetime.now(timezone.utc) - timedelta(seconds=api.AUTO_REFRESH_COOLDOWN_SECONDS + 1),
        "last_success_at": None,
    })())

    with patch("threading.Thread") as thread:
        api._trigger_auto_refresh_if_needed(db, ["weibo"])

    thread.assert_called_once()
    assert thread.call_args.kwargs["target"] is api._run_background_refresh
    assert thread.call_args.kwargs["args"] == (["weibo"],)
    assert thread.call_args.kwargs["daemon"] is True
    thread.return_value.start.assert_called_once()
    assert api._auto_refresh_running is True
    assert api._auto_refresh_platforms == {"weibo"}

    reset_auto_refresh_state()


def test_get_refresh_state_uses_cache_record_fallback():
    db = DummyDB(has_news=True)
    cached = type("CacheRecord", (), {
        "platform": "weibo",
        "last_fetch": datetime(2026, 1, 1, tzinfo=timezone.utc),
    })()
    db.cache_records.append(cached)
    reset_auto_refresh_state()

    state = api._get_refresh_state(db)

    assert state["last_refresh"] == "2026-01-01T00:00:00Z"
    assert state["refreshing"] is False
    assert state["stale"] is True
    assert "weibo" in state["stale_platforms"]


def test_refresh_news_data_updates_cache_records():
    db = DummyDB(has_news=True)

    saved_count, sources = api.refresh_news_data(db, {"weibo": [], "zhihu": [{"platform": "zhihu", "title": "t", "url": "u"}]})

    assert saved_count == 1
    assert sources["weibo"]["status"] == "empty"
    assert sources["zhihu"]["status"] == "success"
    assert [record.platform for record in db.cache_records] == ["weibo", "zhihu"]
