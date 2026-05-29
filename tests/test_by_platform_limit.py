import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api.main import app, get_db


class DummyNews:
    def __init__(self, index):
        self.index = index

    def to_dict(self):
        return {"title": f"新闻{self.index}"}


class DummyNewsQuery:
    def __init__(self):
        self.limit_value = None

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def all(self):
        count = self.limit_value or 0
        return [DummyNews(i) for i in range(count)]


class DummyConfigQuery:
    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None


class DummyDB:
    def query(self, model):
        if model.__name__ == "UserConfig":
            return DummyConfigQuery()
        return DummyNewsQuery()


def test_by_platform_uses_default_limit_per_platform():
    client = TestClient(app)

    def override_get_db():
        yield DummyDB()

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get("/api/news/by_platform")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    first_items = next(iter(response.json()["platforms"].values()))
    assert len(first_items) == 50


def test_by_platform_accepts_smaller_limit_per_platform():
    client = TestClient(app)

    def override_get_db():
        yield DummyDB()

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get("/api/news/by_platform?limit_per_platform=3")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    first_items = next(iter(response.json()["platforms"].values()))
    assert len(first_items) == 3
