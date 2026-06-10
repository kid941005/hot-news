import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.database import save_news
from backend.models.models import News


class DummyDeleteQuery:
    def __init__(self, db):
        self.db = db

    def filter(self, *args, **kwargs):
        return self

    def delete(self):
        self.db.deleted = True

    def first(self):
        return None


class FailingDB:
    def __init__(self):
        self.deleted = False
        self.rolled_back = False

    def query(self, model):
        return DummyDeleteQuery(self)

    def add(self, item):
        raise RuntimeError("add failed")

    def commit(self):
        raise AssertionError("commit should not run")

    def rollback(self):
        self.rolled_back = True


def make_db():
    engine = create_engine("sqlite:///:memory:")
    News.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_save_news_rolls_back_on_write_error():
    db = FailingDB()

    with pytest.raises(RuntimeError):
        save_news(db, [{"platform": "微博", "title": "测试"}])

    assert db.deleted is True
    assert db.rolled_back is True


def test_save_news_keeps_recent_history_and_cleans_older_than_7_days():
    db = make_db()
    now = datetime.utcnow()
    db.add_all([
        News(platform="微博", title="近 7 天旧新闻", url="https://example.com/recent", created_at=now - timedelta(days=6)),
        News(platform="微博", title="超过 7 天旧新闻", url="https://example.com/old", created_at=now - timedelta(days=8)),
    ])
    db.commit()

    save_news(db, [{"platform": "微博", "title": "新新闻", "url": "https://example.com/new"}])

    titles = {item.title for item in db.query(News).filter(News.platform == "微博").all()}
    assert titles == {"近 7 天旧新闻", "新新闻"}


def test_save_news_updates_existing_news_instead_of_duplicating():
    db = make_db()
    db.add(News(platform="微博", title="相同新闻", url="https://example.com/same", hot_value="1"))
    db.commit()

    save_news(db, [{"platform": "微博", "title": "相同新闻", "url": "https://example.com/same", "hot": "2"}])

    rows = db.query(News).filter(News.platform == "微博", News.title == "相同新闻").all()
    assert len(rows) == 1
    assert rows[0].hot_value == "2"
