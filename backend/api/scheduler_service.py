#!/usr/bin/env python3
"""调度状态服务：查询定时任务运行状态，支持暂停/恢复/调整刷新间隔。

设计说明（对标 hotpush 的 scheduler status API）：
- 通过 configure_scheduler 注入 APScheduler 实例，避免与 main 循环导入；
- 任务自身在执行收尾时调用 mark_job_run 记录最近一次结果。
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator

from backend.api.auth import get_current_user_id
from backend.utils import as_utc_iso

logger = logging.getLogger(__name__)

scheduler_router = APIRouter()

UTC = timezone.utc

_scheduler = None  # 由 configure_scheduler 注入
_job_states = {}   # {job_id: {"last_run": iso, "last_result": {...}}}

JOB_IDS = ("refresh_job", "push_job", "token_cleanup_job")



def configure_scheduler(scheduler) -> None:
    """由应用入口注入 BackgroundScheduler 实例。"""
    global _scheduler
    _scheduler = scheduler


def mark_job_run(job_id: str, success: bool, message: str = "") -> None:
    """记录任务最近一次执行结果（任务自身在收尾时调用）。"""
    _job_states[job_id] = {
        "last_run": as_utc_iso(datetime.now(UTC)),
        "last_result": {"success": bool(success), "message": message},
    }


def _get_job_detail(job_id: str) -> dict:
    state = _job_states.get(job_id, {})
    next_run = None
    if _scheduler is not None:
        try:
            job = _scheduler.get_job(job_id)
            next_run = as_utc_iso(job.next_run_time) if job is not None else None
        except Exception:
            logger.warning("读取任务 %s 状态失败", job_id, exc_info=True)
    return {
        "next_run": next_run,
        "last_run": state.get("last_run"),
        "last_result": state.get("last_result"),
    }


def _get_interval_minutes():
    """从 refresh_job 的 IntervalTrigger 读取当前间隔（分钟）。"""
    if _scheduler is None:
        return None
    try:
        job = _scheduler.get_job("refresh_job")
        trigger = getattr(job, "trigger", None)
        interval = getattr(trigger, "interval", None)
        if interval is not None:
            return int(interval.total_seconds() // 60)
    except Exception:
        logger.warning("读取刷新间隔失败", exc_info=True)
    return None


@scheduler_router.get("/api/scheduler")
def get_scheduler_status(user_id: int = Depends(get_current_user_id)):
    """查询调度器运行状态与各任务最近执行结果。"""
    if _scheduler is None:
        return {"success": False, "error": "调度器未初始化"}
    running = bool(getattr(_scheduler, "running", False))
    paused = getattr(_scheduler, "state", 1) == 2
    return {
        "success": True,
        "running": running,
        "paused": paused,
        "interval_minutes": _get_interval_minutes(),
        "refresh_job": _get_job_detail("refresh_job"),
        "push_job": _get_job_detail("push_job"),
        "token_cleanup_job": _get_job_detail("token_cleanup_job"),
    }


@scheduler_router.post("/api/scheduler/pause")
def pause_scheduler(user_id: int = Depends(get_current_user_id)):
    """暂停所有定时任务。"""
    if _scheduler is None or not getattr(_scheduler, "running", False):
        return {"success": False, "error": "调度器未运行"}
    try:
        _scheduler.pause()
    except Exception as exc:
        logger.exception("暂停调度器失败")
        return {"success": False, "error": str(exc)}
    return {"success": True}


@scheduler_router.post("/api/scheduler/resume")
def resume_scheduler(user_id: int = Depends(get_current_user_id)):
    """恢复所有定时任务。"""
    if _scheduler is None or not getattr(_scheduler, "running", False):
        return {"success": False, "error": "调度器未运行"}
    try:
        _scheduler.resume()
    except Exception as exc:
        logger.exception("恢复调度器失败")
        return {"success": False, "error": str(exc)}
    return {"success": True}


class IntervalRequest(BaseModel):
    minutes: int

    @field_validator("minutes")
    @classmethod
    def validate_minutes(cls, value: int) -> int:
        if value < 1 or value > 1440:
            raise ValueError("间隔必须在 1-1440 分钟之间")
        return value


@scheduler_router.post("/api/scheduler/interval")
def update_interval(req: IntervalRequest, user_id: int = Depends(get_current_user_id)):
    """调整新闻自动刷新间隔（分钟）。"""
    if _scheduler is None or not getattr(_scheduler, "running", False):
        return {"success": False, "error": "调度器未运行"}
    try:
        _scheduler.reschedule_job("refresh_job", trigger="interval", minutes=req.minutes)
    except Exception as exc:
        logger.exception("调整刷新间隔失败")
        return {"success": False, "error": str(exc)}
    return {"success": True, "minutes": req.minutes}
