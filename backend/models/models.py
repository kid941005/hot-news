#!/usr/bin/env python3
"""
数据库模型 - 支持MySQL和SQLite
"""
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

Base = declarative_base()


class News(Base):
    """热点资讯"""
    __tablename__ = 'news'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False)
    title = Column(String(500), nullable=False)
    url = Column(String(1000), nullable=False)
    hot_value = Column(String(100), default="")
    pub_time = Column(String(50), default="")
    raw_data = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def to_dict(self):
        return {
            "id": self.id,
            "platform": self.platform,
            "title": self.title,
            "url": self.url,
            "hot_value": self.hot_value,
            "pub_time": self.pub_time,
            "created_at": self.created_at.isoformat() if self.created_at else None
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
    user_id = Column(Integer, ForeignKey('users.id'), unique=True)
    keywords = Column(JSON, default=[])
    blocked_keywords = Column(JSON, default=[])
    keyword_tags = Column(JSON, default={})  # 关键词标签映射 {keyword: tag}
    platforms = Column(JSON, default=[])
    push_enabled = Column(Boolean, default=False)
    push_channel = Column(String(50), default="")
    push_webhook = Column(String(500), default="")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    user = relationship("User", back_populates="config")


class CacheRecord(Base):
    """缓存记录"""
    __tablename__ = 'cache_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False)
    last_fetch = Column(DateTime, default=datetime.now)
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
