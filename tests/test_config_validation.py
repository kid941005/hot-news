import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api.main import app, get_current_user_id, get_db


class DummyDB:
    def __init__(self):
        self.saved = None

    def close(self):
        pass


def test_config_rejects_unknown_platform():
    client = TestClient(app)
    db = DummyDB()

    def override_get_db():
        yield db

    app.dependency_overrides[get_current_user_id] = lambda: 1
    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.post("/api/config", json={"platforms": ["not-a-platform"]})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_config_rejects_too_many_keywords():
    client = TestClient(app)
    db = DummyDB()

    def override_get_db():
        yield db

    app.dependency_overrides[get_current_user_id] = lambda: 1
    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.post("/api/config", json={"keywords": [f"kw{i}" for i in range(101)]})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_config_rejects_invalid_cron():
    client = TestClient(app)
    db = DummyDB()

    def override_get_db():
        yield db

    app.dependency_overrides[get_current_user_id] = lambda: 1
    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.post("/api/config", json={"push_cron": "bad cron"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
