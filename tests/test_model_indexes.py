import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.models.models import News, UserConfig, CacheRecord


def test_news_has_platform_and_id_indexes():
    indexes = {index.name for index in News.__table__.indexes}
    assert "ix_news_platform_id" in indexes


def test_user_config_user_id_is_indexed():
    assert UserConfig.__table__.c.user_id.index is True


def test_cache_record_platform_is_indexed():
    assert CacheRecord.__table__.c.platform.index is True
