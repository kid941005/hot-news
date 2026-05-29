import asyncio
import time
from unittest.mock import patch

from backend.spiders import spiders


class SlowSpider:
    name = "slow"

    def fetch(self):
        time.sleep(0.05)
        return [{"title": self.name}]


class FastSpider:
    name = "fast"

    def fetch(self):
        return [{"title": self.name}]


class FailingSpider:
    name = "fail"

    def fetch(self):
        raise RuntimeError("boom")


class HangingSpider:
    name = "hang"

    def fetch(self):
        time.sleep(0.2)
        return [{"title": self.name}]


def test_fetch_all_spiders_runs_with_limited_concurrency():
    test_spiders = {"a": SlowSpider, "b": SlowSpider, "c": SlowSpider}

    with patch.object(spiders, "SPIDERS", test_spiders), patch.object(spiders, "SPIDER_CONCURRENCY", 3):
        start = time.monotonic()
        results = asyncio.run(spiders.fetch_all_spiders(["a", "b", "c"]))
        elapsed = time.monotonic() - start

    assert set(results.keys()) == {"a", "b", "c"}
    assert elapsed < 0.12


def test_fetch_all_spiders_isolates_platform_errors():
    test_spiders = {"ok": SlowSpider, "bad": FailingSpider}

    with patch.object(spiders, "SPIDERS", test_spiders), patch.object(spiders, "SPIDER_CONCURRENCY", 2):
        results = asyncio.run(spiders.fetch_all_spiders(["ok", "bad", "missing"]))

    assert results["ok"] == [{"title": "slow"}]
    assert results["bad"] == []
    assert "missing" not in results


def test_fetch_all_spiders_times_out_single_platform():
    test_spiders = {"hang": HangingSpider, "ok": FastSpider}

    with patch.object(spiders, "SPIDERS", test_spiders), \
        patch.object(spiders, "SPIDER_CONCURRENCY", 2), \
        patch.object(spiders, "SPIDER_FETCH_TIMEOUT_SECONDS", 0.01):
        results = asyncio.run(spiders.fetch_all_spiders(["hang", "ok"]))

    assert results["hang"] == []
    assert results["ok"] == [{"title": "fast"}]
