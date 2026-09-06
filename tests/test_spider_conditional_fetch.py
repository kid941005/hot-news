import asyncio
import sys
from pathlib import Path
from unittest.mock import Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api import news_service
from backend.db import database
from backend.models.models import CacheRecord
from backend.spiders import spiders
from backend.spiders.spiders import SolidotSpider


def test_fetch_get_raises_not_modified_on_304():
    response = Mock()
    response.status_code = 304

    with patch("backend.spiders.spiders.requests.Session") as session_cls:
        session = session_cls.return_value
        session.get.return_value = response

        try:
            spiders.fetch_get("https://example.com")
            raise AssertionError("expected NotModified")
        except spiders.NotModified:
            pass


def test_define_rss_source_sends_conditional_headers_and_stores_etag():
    spiders.set_conditional_meta({
        "solidot": {"etag": '"old"', "last_modified": "Wed, 10 Jun 2026 09:30:00 GMT"},
    })
    response = Mock()
    response.text = """
    <rss><channel>
      <item><title>Solidot 标题</title><link>https://www.solidot.org/story?sid=1</link></item>
    </channel></rss>
    """
    response.headers = {"ETag": '"new"', "Last-Modified": "Thu, 11 Jun 2026 09:30:00 GMT"}

    try:
        with patch("backend.spiders.spiders.fetch_get", return_value=response) as fetch:
            items = SolidotSpider().fetch()

        assert items[0]["platform"] == "Solidot"
        headers = fetch.call_args.kwargs["headers"]
        assert headers["If-None-Match"] == '"old"'
        assert headers["If-Modified-Since"] == "Wed, 10 Jun 2026 09:30:00 GMT"
        assert spiders.get_conditional_meta("solidot")["etag"] == '"new"'
        assert spiders.get_conditional_meta("solidot")["last_modified"] == "Thu, 11 Jun 2026 09:30:00 GMT"
    finally:
        spiders.set_conditional_meta({})


def test_define_rss_source_returns_unchanged_on_304():
    spiders.set_conditional_meta({"solidot": {"etag": '"old"'}})

    try:
        with patch("backend.spiders.spiders.fetch_get", side_effect=spiders.NotModified("url")):
            result = SolidotSpider().fetch()

        assert result is spiders.UNCHANGED
    finally:
        spiders.set_conditional_meta({})


def test_fetch_all_spiders_propagates_unchanged_sentinel():
    test_spiders = {"solidot": SolidotSpider}
    spiders.set_conditional_meta({"solidot": {"etag": '"old"'}})

    try:
        with patch.object(spiders, "SPIDERS", test_spiders), \
             patch.object(spiders, "SPIDER_CONCURRENCY", 1), \
             patch("backend.spiders.spiders.fetch_get", side_effect=spiders.NotModified("url")):
            results = asyncio.run(spiders.fetch_all_spiders(["solidot"]))

        assert results["solidot"] is spiders.UNCHANGED
    finally:
        spiders.set_conditional_meta({})


def test_fetch_all_spiders_skips_when_another_fetch_in_progress():
    assert spiders._FETCH_LOCK.acquire(blocking=False)
    try:
        results = asyncio.run(spiders.fetch_all_spiders(["solidot"]))
        assert results == {}
    finally:
        spiders._FETCH_LOCK.release()


class DummyCacheQuery:
    def __init__(self, result=None):
        self.result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.result


class DummyDB:
    def __init__(self):
        self.added = []
        self.commits = 0

    def query(self, model):
        return DummyCacheQuery(None)

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.commits += 1


def test_refresh_news_data_keeps_old_data_on_unchanged():
    db = DummyDB()
    spiders.set_conditional_meta({"solidot": {"etag": '"old"'}})

    try:
        saved_count, sources = news_service.refresh_news_data(db, {"solidot": spiders.UNCHANGED})

        assert saved_count == 0
        assert sources["solidot"] == {"status": "unchanged", "count": 0}
        # 304 分支不应写入任何新闻行
        assert all(type(item).__name__ != "News" for item in db.added)
        assert db.commits == 1
    finally:
        spiders.set_conditional_meta({})


def test_update_cache_record_persists_etag_and_last_modified():
    engine = create_engine("sqlite:///:memory:")
    CacheRecord.__table__.create(engine)
    db = sessionmaker(bind=engine)()

    database.update_cache_record(
        db, "solidot", "success",
        etag='"abc"', last_modified="Wed, 10 Jun 2026 09:30:00 GMT",
    )
    meta = database.get_cache_meta_map(db, ["solidot"])

    assert meta == {
        "solidot": {
            "etag": '"abc"',
            "last_modified": "Wed, 10 Jun 2026 09:30:00 GMT",
        }
    }
