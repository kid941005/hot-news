from unittest.mock import patch
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api.main import app, get_current_user_id, get_db, scheduled_push, is_allowed_webhook


class DummyConfig:
    def __init__(self):
        self.user_id = 1
        self.push_enabled = True
        self.push_webhook = "https://open.feishu.cn/open-apis/bot/v2/hook/test"
        self.push_channel = "feishu"
        self.push_cron = "0 */4 * * *"
        self.last_push_at = None
        self.keywords = []
        self.blocked_keywords = []
        self.keyword_tags = {}


class DummyQuery:
    def __init__(self, result):
        self.result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.result

    def all(self):
        return [self.result] if self.result else []


class DummyDB:
    def __init__(self, config):
        self.config = config
        self.commits = 0
        self.closed = False

    def query(self, model):
        return DummyQuery(self.config)

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


def test_manual_push_does_not_refresh_before_push():
    client = TestClient(app)
    db = DummyDB(DummyConfig())
    calls = []

    def override_get_db():
        yield db

    app.dependency_overrides[get_current_user_id] = lambda: 1
    app.dependency_overrides[get_db] = override_get_db

    try:
        with patch("backend.api.main.refresh_news_data", side_effect=AssertionError("manual push should not refresh")):
            with patch("backend.api.main._push_for_user", side_effect=lambda current_db, config: (calls.append(("push", current_db, config)), (True, "ok"))[1]):
                response = client.post("/api/push")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "ok"}
    assert calls[0][0] == "push"
    assert calls[0][1] is db
    assert calls[0][2] is db.config


def test_scheduled_push_does_not_refresh_before_push():
    db = DummyDB(DummyConfig())
    calls = []

    with patch("backend.models.models.SessionLocal", return_value=db):
        with patch("backend.api.main.refresh_news_data", side_effect=AssertionError("scheduled push should not refresh")):
            with patch("backend.api.main._push_for_user", side_effect=lambda current_db, config: (calls.append(("push", current_db, config)), (True, "ok"))[1]):
                scheduled_push()

    assert calls[0][0] == "push"
    assert calls[0][1] is db
    assert calls[0][2] is db.config
    assert db.commits == 1
    assert db.closed is True


def test_webhook_allowlist_rejects_internal_hosts():
    assert not is_allowed_webhook("feishu", "http://open.feishu.cn/open-apis/bot/v2/hook/test")
    assert not is_allowed_webhook("feishu", "https://127.0.0.1/open-apis/bot/v2/hook/test")
    assert not is_allowed_webhook("dingtalk", "https://localhost/robot/send")


def test_webhook_allowlist_accepts_supported_hosts():
    assert is_allowed_webhook("feishu", "https://open.feishu.cn/open-apis/bot/v2/hook/test")
    assert is_allowed_webhook("dingtalk", "https://oapi.dingtalk.com/robot/send?access_token=test")
    assert is_allowed_webhook("bark", "https://api.day.app/test")
