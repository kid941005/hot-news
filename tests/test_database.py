import pytest

from backend.db.database import save_news


class DummyDeleteQuery:
    def __init__(self, db):
        self.db = db

    def filter(self, *args, **kwargs):
        return self

    def delete(self):
        self.db.deleted = True


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


def test_save_news_rolls_back_on_write_error():
    db = FailingDB()

    with pytest.raises(RuntimeError):
        save_news(db, [{"platform": "微博", "title": "测试"}])

    assert db.deleted is True
    assert db.rolled_back is True
