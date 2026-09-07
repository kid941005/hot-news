"""P2 请求驱动惰性刷新测试：每源 interval + 全局 TTL + 定时任务只刷过期源。"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api import news_service as api
from backend.db.database import CacheRecord
from backend.models.models import News
from backend.spiders import spiders


def make_record(platform="weibo", last_success_ago=None, last_fetch_ago=None):
    now = datetime.now(timezone.utc)
    return type("CacheRecord", (), {
        "platform": platform,
        "last_fetch": now - (last_fetch_ago or timedelta(0)),
        "last_success_at": now - last_success_ago if last_success_ago is not None else None,
        "last_error_at": None,
        "last_status": "success",
        "status": "success",
        "error_msg": "",
    })()


class DummyQuery:
    def __init__(self, items=None):
        self.items = items or []

    def distinct(self):
        return self

    def all(self):
        return self.items


class DummyDB:
    def __init__(self, records=None):
        self.records = records or []
        self.closed = False

    def query(self, model):
        if model is CacheRecord:
            return DummyQuery(self.records)
        if model is News or model is News.platform:
            return DummyQuery([("微博热搜",)] if self.records else [])
        raise AssertionError(model)

    def close(self):
        self.closed = True


def test_source_intervals_graded():
    """实时热搜 2min、快讯 5min、慢速 30min、未配置走全局默认。"""
    assert spiders.SOURCE_INTERVALS["weibo"] == 120
    assert spiders.SOURCE_INTERVALS["cls"] == 300
    assert spiders.SOURCE_INTERVALS["zaobao"] == 1800
    assert api._source_interval_seconds("gelonghui") == api.STALE_AFTER_SECONDS


def test_cache_stale_uses_per_source_interval():
    """同一上次成功时间，weibo（120s）视为滞后，zaobao（1800s）仍新鲜。"""
    ago = timedelta(seconds=300)
    weibo = make_record("weibo", last_success_ago=ago)
    zaobao = make_record("zaobao", last_success_ago=ago)
    assert api._is_cache_stale(weibo, "weibo") is True
    assert api._is_cache_stale(zaobao, "zaobao") is False


def test_cache_expired_uses_global_ttl():
    """强制刷新阈值只与全局 TTL 有关，与源 interval 无关。"""
    within = make_record(last_success_ago=timedelta(seconds=api.SOURCE_TTL_SECONDS - 60))
    over = make_record(last_success_ago=timedelta(seconds=api.SOURCE_TTL_SECONDS + 60))
    assert api._is_cache_expired(within, "weibo") is False
    assert api._is_cache_expired(over, "weibo") is True
    assert api._is_cache_expired(over, "zaobao") is True


def test_get_stale_platforms_distinguishes_interval_and_ttl():
    """状态展示用源 interval；实际刷新（for_refresh=True）用全局 TTL。"""
    db = DummyDB([
        make_record("weibo", last_success_ago=timedelta(seconds=300)),
        make_record("zaobao", last_success_ago=timedelta(seconds=300)),
        make_record(
            "weibo",
            last_success_ago=timedelta(seconds=api.SOURCE_TTL_SECONDS + 1),
            last_fetch_ago=timedelta(seconds=api.AUTO_REFRESH_COOLDOWN_SECONDS + 1),
        ),
    ])
    records = db.query(CacheRecord).all()

    stale = api._get_stale_platforms(db, ["weibo", "zaobao"], records=records)
    assert stale == ["weibo"]

    expired = api._get_stale_platforms(db, ["weibo", "zaobao"], records=records, for_refresh=True)
    assert expired == ["weibo"]


def test_scheduled_refresh_skips_when_no_expired_source():
    db = DummyDB()
    calls = []

    with patch.object(api, "SessionLocal", return_value=db), \
         patch.object(api, "_get_stale_platforms", return_value=[]), \
         patch.object(api, "refresh_news_data", side_effect=lambda *a, **k: calls.append((a, k)) or (0, {})), \
         patch.object(api.scheduler_service, "mark_job_run") as mark:
        api.scheduled_refresh()

    assert calls == []
    mark.assert_called_once_with("refresh_job", True, "无过期源，跳过")
    assert db.closed is True


def test_scheduled_refresh_fetches_only_expired_sources():
    db = DummyDB()
    calls = []

    with patch.object(api, "SessionLocal", return_value=db), \
         patch.object(api, "_get_stale_platforms", return_value=["weibo", "zaobao"]), \
         patch.object(api, "refresh_news_data", side_effect=lambda db, platforms: calls.append(platforms) or (2, {})), \
         patch.object(api.scheduler_service, "mark_job_run") as mark:
        api.scheduled_refresh()

    assert calls == [["weibo", "zaobao"]]
    mark.assert_called_once()


def test_get_refresh_state_exposes_interval_and_next_refresh():
    db = DummyDB([make_record("weibo", last_success_ago=timedelta(seconds=60))])
    state = api._get_refresh_state(db, ["weibo"])
    src = state["sources"]["weibo"]
    assert src["interval_seconds"] == 120
    assert src["next_refresh_at"] is not None
    assert src["has_cache"] is True
