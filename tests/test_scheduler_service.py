import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api import scheduler_service
from backend.api.auth import get_current_user_id
from backend.api.main import app


class DummyScheduler:
    def __init__(self, running=True, state=1):
        self.running = running
        self.state = state
        self.pause_calls = 0
        self.resume_calls = 0
        self.rescheduled = []

    def get_job(self, job_id):
        if job_id == "refresh_job":
            trigger = SimpleNamespace(interval=SimpleNamespace(total_seconds=lambda: 900))
            return SimpleNamespace(
                next_run_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
                trigger=trigger,
            )
        return None

    def pause(self):
        self.pause_calls += 1
        self.state = 2

    def resume(self):
        self.resume_calls += 1
        self.state = 1

    def reschedule_job(self, job_id, **kwargs):
        self.rescheduled.append((job_id, kwargs))


@pytest.fixture(autouse=True)
def _clean_scheduler_state():
    scheduler_service.configure_scheduler(None)
    scheduler_service._job_states.clear()
    yield
    scheduler_service.configure_scheduler(None)
    scheduler_service._job_states.clear()


def _client():
    client = TestClient(app)
    client.app.dependency_overrides[get_current_user_id] = lambda: 1
    return client


def test_scheduler_status_reports_jobs_and_states():
    scheduler = DummyScheduler()
    scheduler_service.configure_scheduler(scheduler)
    scheduler_service.mark_job_run("refresh_job", True, "共保存 100 条新闻")
    client = _client()
    try:
        response = client.get("/api/scheduler")
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["running"] is True
    assert data["paused"] is False
    assert data["interval_minutes"] == 15
    assert data["refresh_job"]["next_run"] == "2026-01-01T00:00:00Z"
    assert data["refresh_job"]["last_result"] == {"success": True, "message": "共保存 100 条新闻"}
    assert data["push_job"]["next_run"] is None
    assert data["token_cleanup_job"]["last_run"] is None


def test_scheduler_status_uninitialized():
    client = _client()
    try:
        response = client.get("/api/scheduler")
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"success": False, "error": "调度器未初始化"}


def test_pause_scheduler():
    scheduler = DummyScheduler()
    scheduler_service.configure_scheduler(scheduler)
    client = _client()
    try:
        response = client.post("/api/scheduler/pause")
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert scheduler.pause_calls == 1
    assert scheduler.state == 2


def test_resume_scheduler():
    scheduler = DummyScheduler(state=2)
    scheduler_service.configure_scheduler(scheduler)
    client = _client()
    try:
        response = client.post("/api/scheduler/resume")
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert scheduler.resume_calls == 1
    assert scheduler.state == 1


def test_pause_scheduler_when_not_running():
    scheduler = DummyScheduler(running=False)
    scheduler_service.configure_scheduler(scheduler)
    client = _client()
    try:
        response = client.post("/api/scheduler/pause")
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"success": False, "error": "调度器未运行"}
    assert scheduler.pause_calls == 0


def test_update_interval():
    scheduler = DummyScheduler()
    scheduler_service.configure_scheduler(scheduler)
    client = _client()
    try:
        response = client.post("/api/scheduler/interval", json={"minutes": 30})
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"success": True, "minutes": 30}
    assert scheduler.rescheduled == [("refresh_job", {"trigger": "interval", "minutes": 30})]


def test_update_interval_rejects_out_of_range():
    scheduler = DummyScheduler()
    scheduler_service.configure_scheduler(scheduler)
    client = _client()
    try:
        response = client.post("/api/scheduler/interval", json={"minutes": 0})
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 422
    assert scheduler.rescheduled == []
