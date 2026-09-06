#!/usr/bin/env python3
"""统一环境变量配置（基于 pydantic-settings）。

后端所有数值型/列表型配置集中在此定义，避免各处散落的 os.getenv + 手工校验。
配置非法时启动即报错（fail fast），防止静默使用错误参数。
"""
from functools import lru_cache
from typing import List, Optional, Set

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- 调度与刷新 ----
    refresh_interval_minutes: int = Field(15, ge=1, le=1440)
    refresh_cooldown_seconds: int = Field(300, ge=0, le=86400)
    auto_refresh_cooldown_seconds: int = Field(30, ge=5, le=3600)
    stale_after_seconds: int = Field(600, ge=30, le=86400)

    # ---- 爬虫 ----
    spider_concurrency: int = Field(5, ge=1, le=20)
    spider_fetch_timeout_seconds: float = Field(15.0, ge=1.0, le=60.0)

    # ---- 应用 ----
    cors_origins: str = "*"
    database_url: Optional[str] = None

    # ---- 推送 ----
    bark_webhook_hosts: str = "api.day.app"

    # ---- MCP ----
    mcp_host: str = "127.0.0.1"
    mcp_port: int = Field(8000, ge=1, le=65535)
    mcp_path: str = "/mcp"
    mcp_transport: str = "stdio"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def bark_webhook_hosts_set(self) -> Set[str]:
        return {h.strip().lower() for h in self.bark_webhook_hosts.split(",") if h.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
