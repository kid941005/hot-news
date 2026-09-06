import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.config import Settings


def test_settings_defaults():
    s = Settings(_env_file=None)
    assert s.refresh_interval_minutes == 15
    assert s.refresh_cooldown_seconds == 300
    assert s.auto_refresh_cooldown_seconds == 30
    assert s.spider_concurrency == 5
    assert s.spider_fetch_timeout_seconds == 15.0
    assert s.cors_origins_list == ["*"]
    assert s.bark_webhook_hosts_set == {"api.day.app"}


def test_settings_reads_env_and_normalizes_lists(monkeypatch):
    monkeypatch.setenv("REFRESH_INTERVAL_MINUTES", "30")
    monkeypatch.setenv("SPIDER_CONCURRENCY", "8")
    monkeypatch.setenv("SPIDER_FETCH_TIMEOUT_SECONDS", "20.5")
    monkeypatch.setenv("CORS_ORIGINS", "https://a.com, https://b.com")
    monkeypatch.setenv("BARK_WEBHOOK_HOSTS", "api.day.app, push.example.com")

    s = Settings(_env_file=None)

    assert s.refresh_interval_minutes == 30
    assert s.spider_concurrency == 8
    assert s.spider_fetch_timeout_seconds == 20.5
    assert s.cors_origins_list == ["https://a.com", "https://b.com"]
    assert s.bark_webhook_hosts_set == {"api.day.app", "push.example.com"}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"refresh_interval_minutes": 0},
        {"refresh_interval_minutes": 1441},
        {"spider_concurrency": 21},
        {"spider_fetch_timeout_seconds": 0.5},
        {"mcp_port": 0},
    ],
)
def test_settings_rejects_out_of_range(kwargs):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **kwargs)
