import sys
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api.main import app, get_db


class DummyDB:
    def __init__(self):
        self.rollbacks = 0

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


def test_register_hides_internal_error_detail():
    client = TestClient(app)
    db = DummyDB()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with patch("backend.api.main.database.create_user", side_effect=RuntimeError("internal db detail")):
            response = client.post("/api/register", json={"username": "u", "password": "p"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"success": False, "error": "注册失败"}
    assert db.rollbacks == 1


def test_register_duplicate_user_returns_stable_message():
    client = TestClient(app)
    db = DummyDB()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with patch("backend.api.main.database.create_user", side_effect=IntegrityError("stmt", "params", Exception("orig"))):
            response = client.post("/api/register", json={"username": "u", "password": "p"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"success": False, "error": "用户名已存在"}
    assert db.rollbacks == 1
