#!/usr/bin/env python3
"""
数据库模型 - 支持MySQL和SQLite
"""
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey, Index
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

Base = declarative_base()


class News(Base):
    """热点资讯"""
    __tablename__ = 'news'
    __table_args__ = (Index('ix_news_platform_id', 'platform', 'id'),)
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False)
    title = Column(String(500), nullable=False)
    url = Column(String(1000), nullable=False)
    hot_value = Column(String(100), default="")
    pub_time = Column(String(50), default="")
    raw_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "platform": self.platform,
            "title": self.title,
            "url": self.url,
            "hot_value": self.hot_value,
            "pub_time": self.pub_time,
            "created_at": (self.created_at.isoformat() + "Z") if self.created_at else None
        }


class User(Base):
    """用户"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    
    config = relationship("UserConfig", back_populates="user", uselist=False)


class UserConfig(Base):
    """用户配置"""
    __tablename__ = 'user_configs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True, index=True)
    keywords = Column(JSON, default=list)
    blocked_keywords = Column(JSON, default=list)
    keyword_tags = Column(JSON, default=dict)  # 标签关键词映射 {tag: [keywords]}
    platforms = Column(JSON, default=list)
    push_enabled = Column(Boolean, default=False)
    push_channel = Column(String(50), default="")
    push_webhook = Column(String(500), default="")
    push_cron = Column(String(50), default="0 */4 * * *")  # cron 表达式
    last_push_at = Column(DateTime, nullable=True)  # 最后一次成功推送时间
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="config")


def ensure_user_config_schema():
    conn = engine.raw_connection()
    try:
        cur = conn.cursor()
        if 'mysql' in DB_URL:
            cur.execute("SHOW COLUMNS FROM user_configs")
            cols = {r[0] for r in cur.fetchall()}
        elif 'sqlite' in DB_URL:
            cur.execute("PRAGMA table_info(user_configs)")
            cols = {r[1] for r in cur.fetchall()}
        else:
            cols = set()
        for column in ['push_cron', 'last_push_at']:
            if column not in cols:
                if column == 'push_cron':
                    cur.execute("ALTER TABLE user_configs ADD COLUMN push_cron VARCHAR(50) NOT NULL DEFAULT '0 */4 * * *'")
                else:
                    cur.execute("ALTER TABLE user_configs ADD COLUMN last_push_at DATETIME")
                conn.commit()
    finally:
        conn.close()


class CacheRecord(Base):
    """缓存记录"""
    __tablename__ = 'cache_records'
    __table_args__ = (Index('ix_cache_records_platform', 'platform'),)
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False, index=True)
    last_fetch = Column(DateTime, default=datetime.now)
    last_success_at = Column(DateTime, nullable=True)
    last_error_at = Column(DateTime, nullable=True)
    last_status = Column(String(20), default="success")
    status = Column(String(20), default="success")
    error_msg = Column(Text, default="")


# 数据库连接
def get_database_url():
    """获取数据库URL"""
    db_url = os.environ.get('DATABASE_URL', '')
    
    if db_url:
        return db_url
    
    # 默认SQLite
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hot_news.db")
    return f"sqlite:///{db_path}"


DB_URL = get_database_url()

# 根据数据库类型选择连接参数
if "mysql" in DB_URL:
    engine = create_engine(DB_URL, pool_pre_ping=True, pool_recycle=3600)
else:
    engine = create_engine(DB_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """初始化数据库"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
