import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api import main as api
from backend.models.models import News


async def fake_fetch_all_spiders():
    return {"weibo": [{"title": "测试"}]}


class DummyQuery:
    def __init__(self, item):
        self.item = item

    def first(self):
        return self.item


class DummyDB:
    def __init__(self, has_news):
        self.has_news = has_news

    def query(self, model):
        assert model is News
        return DummyQuery(object() if self.has_news else None)


def reset_auto_refresh_state():
    api.LAST_REFRESH_TIME = None
    api._auto_refresh_running = False


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


def test_auto_refresh_skips_during_cooldown():
    api.LAST_REFRESH_TIME = datetime.now(timezone.utc)
    api._auto_refresh_running = False

    with patch("threading.Thread") as thread:
        api._trigger_auto_refresh_if_needed(DummyDB(has_news=True))

    thread.assert_not_called()
    assert api._auto_refresh_running is False


def test_auto_refresh_starts_background_thread_when_data_is_stale():
    api.LAST_REFRESH_TIME = datetime.now(timezone.utc) - timedelta(seconds=api.AUTO_REFRESH_COOLDOWN_SECONDS + 1)
    api._auto_refresh_running = False

    with patch("threading.Thread") as thread:
        api._trigger_auto_refresh_if_needed(DummyDB(has_news=True))

    thread.assert_called_once()
    assert thread.call_args.kwargs["target"] is api._run_background_refresh
    assert thread.call_args.kwargs["daemon"] is True
    thread.return_value.start.assert_called_once()
    assert api._auto_refresh_running is True

    reset_auto_refresh_state()
