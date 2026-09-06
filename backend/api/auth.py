#!/usr/bin/env python3
"""
认证模块：Token 管理、登录/注册限流与认证依赖。
"""
import logging
import secrets
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.db import database
from backend.models.models import get_db

logger = logging.getLogger(__name__)

auth_router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("用户名不能为空")
        if len(value) > 50:
            raise ValueError("用户名最多 50 个字符")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not value:
            raise ValueError("密码不能为空")
        if len(value) < 6:
            raise ValueError("密码至少 6 个字符")
        return value


# token 内存缓存：优先查询，未命中时回退到数据库 user_tokens 表
_tokens: Dict[str, tuple] = {}  # {token: (user_id, expires_at)}

# 登录/注册限流（进程内存，15 分钟窗口；多实例部署时建议换 Redis）
_LOGIN_ATTEMPTS: Dict[str, list] = {}
_LOGIN_ATTEMPTS_LOCK = threading.Lock()
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 15 * 60


def _is_login_rate_limited(client_ip: str) -> bool:
    with _LOGIN_ATTEMPTS_LOCK:
        now = datetime.now()
        attempts = [
            ts for ts in _LOGIN_ATTEMPTS.get(client_ip, [])
            if (now - ts).total_seconds() < LOGIN_WINDOW_SECONDS
        ]
        # 只保留窗口内最近的尝试，防止字典无限增长
        _LOGIN_ATTEMPTS[client_ip] = attempts[-LOGIN_MAX_ATTEMPTS:]
        return len(attempts) >= LOGIN_MAX_ATTEMPTS


def _record_login_attempt(client_ip: str) -> None:
    with _LOGIN_ATTEMPTS_LOCK:
        _LOGIN_ATTEMPTS.setdefault(client_ip, []).append(datetime.now())


def _clear_login_attempts(client_ip: str) -> None:
    with _LOGIN_ATTEMPTS_LOCK:
        _LOGIN_ATTEMPTS.pop(client_ip, None)


def generate_token(user_id: int, expires_hours: int = 24 * 7, db: Optional[Session] = None) -> str:
    """生成 token 并持久化；数据库不可用时降级为纯内存存储。"""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=expires_hours)
    _tokens[token] = (user_id, expires_at)
    if db is not None:
        try:
            database.save_token(db, token, user_id, expires_at)
        except Exception:
            logger.warning("令牌持久化失败，降级为内存存储", exc_info=True)
    return token


def cleanup_expired_tokens(now: Optional[datetime] = None, db: Optional[Session] = None) -> int:
    """清理过期 token（内存 + 数据库），返回清理数量。"""
    now = now or datetime.now()
    expired = [token for token, (_, expires_at) in _tokens.items() if now > expires_at]
    for token in expired:
        del _tokens[token]
    if db is not None:
        try:
            database.delete_expired_tokens(db, now)
        except Exception:
            logger.warning("过期令牌数据库清理失败", exc_info=True)
    return len(expired)


def verify_token(token: str, db: Optional[Session] = None) -> Optional[int]:
    """验证 token，返回 user_id；内存未命中时回退到数据库。"""
    if not token:
        return None
    record = _tokens.get(token)
    if record is not None:
        user_id, expires_at = record
        if datetime.now() > expires_at:
            del _tokens[token]
            return None
        return user_id
    if db is None:
        return None
    try:
        row = database.get_token(db, token)
    except Exception:
        logger.warning("令牌数据库查询失败", exc_info=True)
        row = None
    if row is None:
        return None
    if datetime.now() > row.expires_at:
        try:
            database.delete_token_record(db, row.token)
        except Exception:
            logger.warning("过期令牌数据库删除失败", exc_info=True)
        return None
    _tokens[token] = (row.user_id, row.expires_at)
    return row.user_id


def delete_token(token: str, db: Optional[Session] = None):
    """删除 token（内存 + 数据库）"""
    if token in _tokens:
        del _tokens[token]
    if db is not None:
        try:
            database.delete_token_record(db, token)
        except Exception:
            logger.warning("令牌数据库删除失败", exc_info=True)


def get_optional_user_id(
    Authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Optional[int]:
    """获取可选用户ID - 无有效 token 时返回 None"""
    if Authorization and Authorization.startswith("Bearer "):
        token = Authorization[7:]
        return verify_token(token, db)
    return None


def get_current_user_id(
    Authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> int:
    """获取当前用户ID - 从 Authorization header 获取 token"""
    user_id = get_optional_user_id(Authorization, db)
    if user_id:
        return user_id
    raise HTTPException(status_code=401, detail="未认证")


@auth_router.post("/api/register")
def register(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    if _is_login_rate_limited(client_ip):
        return {"success": False, "error": "尝试次数过多，请稍后再试"}
    try:
        user = database.create_user(db, req.username, req.password)
        _clear_login_attempts(client_ip)
        token = generate_token(user.id, db=db)
        return {"success": True, "username": user.username, "user_id": user.id, "token": token}
    except IntegrityError:
        db.rollback()
        _record_login_attempt(client_ip)
        return {"success": False, "error": "用户名已存在"}
    except Exception:
        db.rollback()
        _record_login_attempt(client_ip)
        logger.exception("注册失败")
        return {"success": False, "error": "注册失败"}


@auth_router.post("/api/login")
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    if _is_login_rate_limited(client_ip):
        return {"success": False, "error": "尝试次数过多，请稍后再试"}
    user = database.verify_user(db, req.username, req.password)
    if user:
        _clear_login_attempts(client_ip)
        token = generate_token(user.id, db=db)
        return {"success": True, "username": user.username, "user_id": user.id, "token": token}
    _record_login_attempt(client_ip)
    return {"success": False, "error": "用户名或密码错误"}


@auth_router.post("/api/logout")
def logout(Authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    if Authorization and Authorization.startswith("Bearer "):
        token = Authorization[7:]
        delete_token(token, db)
    return {"success": True}
