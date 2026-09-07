#!/usr/bin/env python3
"""
FastAPI 应用入口：组装业务路由、静态资源与定时任务调度。
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from apscheduler.schedulers.background import BackgroundScheduler

from backend.api.auth import auth_router, cleanup_expired_tokens
from backend.api.config_service import config_router
from backend.api.news_service import news_router, scheduled_refresh
from backend.api.push_service import push_router, scheduled_push
from backend.api.scheduler_service import configure_scheduler, scheduler_router
from backend.config import settings
from backend.logging_config import setup_logging
from backend.models.models import SessionLocal, ensure_user_config_schema, init_db

setup_logging()
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
REFRESH_INTERVAL_MINUTES = settings.refresh_interval_minutes

# 静态文件路径
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_runtime()
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(title="热点资讯", version="2.5.69", lifespan=lifespan)

# CORS
CORS_ORIGINS = settings.cors_origins_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials="*" not in CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 业务路由
app.include_router(auth_router)
app.include_router(config_router)
app.include_router(news_router)
app.include_router(push_router)
app.include_router(scheduler_router)

# ============= 前端页面 =============

FALLBACK_PAGE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>热点资讯</title></head>
<body>
    <h1>前端静态文件未构建</h1>
    <p>请先在 frontend 目录运行 npm run build，并将构建产物部署到 backend/api/static。</p>
</body>
</html>
"""


# 说明：下方 "/" 路由与 init_runtime 中的 StaticFiles 挂载并存是有意设计——
# 挂载负责 /assets、/icons 等全部静态文件；显式 "/" 路由则保证在静态文件
# 缺失（未构建前端）时返回友好的构建提示页，而不是 404。
@app.get("/", response_class=HTMLResponse)
def index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return FALLBACK_PAGE


def init_runtime():
    init_db()
    ensure_user_config_schema()
    # 挂载静态文件（含 index.html 兜底；"/" 显式路由注册在前，优先命中）
    if os.path.exists(STATIC_DIR):
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


def start_scheduler():
    """启动定时任务调度器"""
    if scheduler.running:
        logger.info("⏰ 定时任务调度器已启动，跳过重复启动")
        return
    scheduler.add_job(scheduled_refresh, 'interval', minutes=REFRESH_INTERVAL_MINUTES, id='refresh_job', replace_existing=True)
    scheduler.add_job(scheduled_push, 'interval', minutes=1, id='push_job', replace_existing=True)
    scheduler.add_job(_cleanup_expired_tokens_job, 'interval', hours=1, id='token_cleanup_job', replace_existing=True)
    scheduler.start()
    configure_scheduler(scheduler)
    logger.info("⏰ 定时刷新已启动（每 %s 分钟抓取一次）", REFRESH_INTERVAL_MINUTES)
    logger.info("⏰ 定时推送已启动（每分钟检查 cron 表达式）")


def stop_scheduler():
    """关闭定时推送调度器"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("⏰ 定时推送已关闭")


def _cleanup_expired_tokens_job():
    """清理过期令牌（含数据库持久化层）"""
    db = SessionLocal()
    try:
        cleanup_expired_tokens(db=db)
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=16888)
