import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api import main
from backend.api.main import app, get_db


class DummyNews:
    def __init__(self, index):
        self.index = index

    def to_dict(self):
        return {"title": f"新闻{self.index}"}


class RecordingNewsQuery:
    def __init__(self, db):
        self.db = db
        self.limit_value = None
        self.platform = None
        self.order = None

    def filter(self, condition):
        self.platform = condition.right.value
        return self

    def order_by(self, order, *args, **kwargs):
        self.order = str(order)
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def all(self):
        self.db.platform_filters.append(self.platform)
        self.db.orders.append(self.order)
        count = self.limit_value or 0
        return [DummyNews(i) for i in range(count)]

    def first(self):
        return DummyNews(0)


class DummyConfigQuery:
    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None


class DummyCacheRecordQuery:
    """Mock query returning a fresh cache record so _get_stale_platforms is empty."""

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        now = datetime.now(timezone.utc)
        return type("CacheRecord", (), {
            "platform": "weibo",
            "last_fetch": now,
            "last_success_at": now,
        })()


class DummyDB:
    def __init__(self):
        self.platform_filters = []
        self.orders = []

    def query(self, model):
        if model.__name__ == "UserConfig":
            return DummyConfigQuery()
        if model.__name__ == "CacheRecord":
            return DummyCacheRecordQuery()
        return RecordingNewsQuery(self)


def test_by_platform_uses_default_limit_per_platform():
    client = TestClient(app)

    db = DummyDB()

    def override_get_db():
        yield db

    old_last = main.LAST_REFRESH_TIME
    old_running = main._auto_refresh_running
    main.LAST_REFRESH_TIME = datetime.now(timezone.utc)
    main._auto_refresh_running = False
    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get("/api/news/by_platform")
    finally:
        main.LAST_REFRESH_TIME = old_last
        main._auto_refresh_running = old_running
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()["platforms"]
    first_items = next(iter(data.values()))
    assert len(first_items) == 50
    assert "微博热搜" in data
    assert "weibo" not in db.platform_filters
    assert any("ASC" in order.upper() for order in db.orders if order)


def test_by_platform_accepts_timeline_sort():
    client = TestClient(app)

    db = DummyDB()

    def override_get_db():
        yield db

    old_last = main.LAST_REFRESH_TIME
    old_running = main._auto_refresh_running
    main.LAST_REFRESH_TIME = datetime.now(timezone.utc)
    main._auto_refresh_running = False
    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get("/api/news/by_platform?sort=timeline")
    finally:
        main.LAST_REFRESH_TIME = old_last
        main._auto_refresh_running = old_running
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert any("DESC" in order.upper() for order in db.orders if order)


def test_by_platform_accepts_smaller_limit_per_platform():
    client = TestClient(app)

    db = DummyDB()

    def override_get_db():
        yield db

    old_last = main.LAST_REFRESH_TIME
    old_running = main._auto_refresh_running
    main.LAST_REFRESH_TIME = datetime.now(timezone.utc)
    main._auto_refresh_running = False
    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get("/api/news/by_platform?limit_per_platform=3")
    finally:
        main.LAST_REFRESH_TIME = old_last
        main._auto_refresh_running = old_running
        app.dependency_overrides.clear()

    assert response.status_code == 200
    first_items = next(iter(response.json()["platforms"].values()))
    assert len(first_items) == 3
