import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api import main
from backend.api.main import app, get_current_user_id, get_db


class DummyDB:
    def close(self):
        pass


def test_manual_refresh_returns_cooldown_without_fetching():
    client = TestClient(app)
    db = DummyDB()

    def override_get_db():
        yield db

    app.dependency_overrides[get_current_user_id] = lambda: 1
    app.dependency_overrides[get_db] = override_get_db

    old_last = main.LAST_REFRESH_TIME
    old_cooldown = main.REFRESH_COOLDOWN_SECONDS
    main.LAST_REFRESH_TIME = datetime.now(timezone.utc)
    main.REFRESH_COOLDOWN_SECONDS = 300
    try:
        with patch("backend.api.main.spiders.fetch_all_spiders", side_effect=AssertionError("should not fetch during cooldown")):
            response = client.post("/api/news/refresh")
    finally:
        main.LAST_REFRESH_TIME = old_last
        main.REFRESH_COOLDOWN_SECONDS = old_cooldown
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert "刷新太频繁" in body["error"]
