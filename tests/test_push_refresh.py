from unittest.mock import patch
from types import SimpleNamespace
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api.main import app, get_current_user_id, get_db, scheduled_push, is_allowed_webhook, _push_for_user, push_to_feishu


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


def test_push_content_deduplicates_same_news_in_multiple_tags():
    config = DummyConfig()
    config.keyword_tags = {"工作": ["AI"], "科技": ["模型"]}
    db = DummyDB(config)
    news = SimpleNamespace(id=1, platform="微博", title="AI 模型发布", url="https://example.com/news")

    with patch("backend.api.main.database.get_user_filtered_news", return_value=([news], {1: ["AI", "模型"]})):
        with patch("backend.api.main.push_to_feishu", return_value=True) as push:
            success, message = _push_for_user(db, config)

    assert success is True
    assert message == "成功推送1条新闻"
    content = push.call_args.args[1]
    assert content.count("AI 模型发布") == 1
    assert "[微博] [AI 模型发布](https://example.com/news)" in content


def test_push_content_deduplicates_same_title_across_news():
    config = DummyConfig()
    db = DummyDB(config)
    news_list = [
        SimpleNamespace(id=1, platform="微博", title="相同标题", url="https://example.com/1"),
        SimpleNamespace(id=2, platform="知乎", title="相同标题", url="https://example.com/2"),
    ]

    with patch("backend.api.main.database.get_user_filtered_news", return_value=(news_list, {1: [], 2: []})):
        with patch("backend.api.main.push_to_feishu", return_value=True) as push:
            success, message = _push_for_user(db, config)

    assert success is True
    assert message == "成功推送1条新闻"
    content = push.call_args.args[1]
    assert content.count("相同标题") == 1
    assert "https://example.com/1" in content
    assert "https://example.com/2" not in content


def test_push_content_keeps_platform_in_untagged_news():
    config = DummyConfig()
    db = DummyDB(config)
    news = SimpleNamespace(id=1, platform="知乎", title="行业观察", url="https://example.com/zhihu")

    with patch("backend.api.main.database.get_user_filtered_news", return_value=([news], {1: []})):
        with patch("backend.api.main.push_to_feishu", return_value=True) as push:
            success, message = _push_for_user(db, config)

    assert success is True
    assert message == "成功推送1条新闻"
    assert "[知乎] [行业观察](https://example.com/zhihu)" in push.call_args.args[1]


def test_webhook_allowlist_rejects_internal_hosts():
    assert not is_allowed_webhook("feishu", "http://open.feishu.cn/open-apis/bot/v2/hook/test")
    assert not is_allowed_webhook("feishu", "https://127.0.0.1/open-apis/bot/v2/hook/test")
    assert not is_allowed_webhook("dingtalk", "https://localhost/robot/send")


def test_webhook_allowlist_accepts_supported_hosts():
    assert is_allowed_webhook("feishu", "https://open.feishu.cn/open-apis/bot/v2/hook/test")
    assert is_allowed_webhook("dingtalk", "https://oapi.dingtalk.com/robot/send?access_token=test")
    assert is_allowed_webhook("bark", "https://api.day.app/test")


def test_push_to_feishu_uses_post_payload_for_links():
    captured = {}

    class DummyResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"code": 0}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return DummyResponse()

    with patch("requests.post", side_effect=fake_post):
        success = push_to_feishu(
            "https://open.feishu.cn/open-apis/bot/v2/hook/test",
            "📰 热点资讯 (12:00)\n\n### 科技\n1. [微博] [AI 模型发布](https://example.com/news)\n",
        )

    assert success is True
    assert captured["timeout"] == 10
    assert captured["json"]["msg_type"] == "post"
    assert captured["json"]["content"]["post"]["zh_cn"]["title"] == "📰 热点资讯 (12:00)"
    assert captured["json"]["content"]["post"]["zh_cn"]["content"][0] == [{"tag": "text", "text": "科技"}]
    assert captured["json"]["content"]["post"]["zh_cn"]["content"][1] == [
        {"tag": "text", "text": "1. [微博] "},
        {"tag": "a", "text": "AI 模型发布", "href": "https://example.com/news"},
    ]
