import sys
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api import auth
from backend.db import database
from backend.models.models import Base, User


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(User(username="tester", password_hash="x"))
    db.commit()
    return db


def test_token_survives_restart_via_database():
    auth._tokens.clear()
    db = make_db()
    try:
        token = auth.generate_token(1, db=db)

        # 模拟服务重启：清空内存缓存后，令牌仍可通过数据库校验
        auth._tokens.clear()
        assert auth.verify_token(token, db) == 1
        assert auth._tokens[token][0] == 1
    finally:
        auth._tokens.clear()
        db.close()


def test_delete_token_removes_database_record():
    auth._tokens.clear()
    db = make_db()
    try:
        token = auth.generate_token(1, db=db)
        assert database.get_token(db, token) is not None

        auth.delete_token(token, db)

        assert database.get_token(db, token) is None
        assert auth.verify_token(token, db) is None
    finally:
        auth._tokens.clear()
        db.close()


def test_cleanup_expired_tokens_removes_database_rows():
    auth._tokens.clear()
    db = make_db()
    try:
        now = datetime.now()
        expired = auth.generate_token(1, db=db)
        # 手动将令牌与数据库记录置为已过期
        auth._tokens[expired] = (1, now - timedelta(seconds=1))
        row = database.get_token(db, expired)
        row.expires_at = now - timedelta(seconds=1)
        db.commit()

        removed = auth.cleanup_expired_tokens(now, db)

        assert removed == 1
        assert database.get_token(db, expired) is None
        assert auth.verify_token(expired, db) is None
    finally:
        auth._tokens.clear()
        db.close()
