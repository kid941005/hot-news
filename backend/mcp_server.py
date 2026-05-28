#!/usr/bin/env python3
"""Hot News MCP server."""
import argparse
import os
from typing import Optional

from mcp.server.fastmcp import FastMCP

from backend.db.database import PLATFORM_MAP
from backend.models.models import News, SessionLocal, init_db

mcp = FastMCP(
    "hot-news",
    host=os.getenv("MCP_HOST", "127.0.0.1"),
    port=int(os.getenv("MCP_PORT", "8000")),
    streamable_http_path=os.getenv("MCP_PATH", "/mcp"),
)


def _news_to_dict(news: News) -> dict:
    return news.to_dict()


@mcp.tool()
def list_platforms() -> list[dict]:
    """List supported news platforms."""
    return [{"id": k, "name": v} for k, v in PLATFORM_MAP.items()]


@mcp.tool()
def get_latest_news(platform: Optional[str] = None, limit: int = 20) -> list[dict]:
    """Get latest news. Platform can be an id like 'weibo' or a Chinese name like '微博'."""
    limit = max(1, min(limit, 100))
    db = SessionLocal()
    try:
        query = db.query(News)
        if platform:
            query = query.filter(News.platform == PLATFORM_MAP.get(platform, platform))
        rows = query.order_by(News.id.desc()).limit(limit).all()
        return [_news_to_dict(row) for row in rows]
    finally:
        db.close()


@mcp.tool()
def search_news(keyword: str, platform: Optional[str] = None, limit: int = 20) -> list[dict]:
    """Search news titles by keyword."""
    limit = max(1, min(limit, 100))
    db = SessionLocal()
    try:
        query = db.query(News).filter(News.title.contains(keyword))
        if platform:
            query = query.filter(News.platform == PLATFORM_MAP.get(platform, platform))
        rows = query.order_by(News.id.desc()).limit(limit).all()
        return [_news_to_dict(row) for row in rows]
    finally:
        db.close()


@mcp.tool()
def get_news_by_platform(limit_per_platform: int = 20) -> dict:
    """Get latest news grouped by platform."""
    limit_per_platform = max(1, min(limit_per_platform, 100))
    db = SessionLocal()
    try:
        result = {}
        for platform in PLATFORM_MAP.values():
            rows = (
                db.query(News)
                .filter(News.platform == platform)
                .order_by(News.id.desc())
                .limit(limit_per_platform)
                .all()
            )
            if rows:
                result[platform] = [_news_to_dict(row) for row in rows]
        return result
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Hot News MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
    )
    args = parser.parse_args()
    init_db()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
