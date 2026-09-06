#!/usr/bin/env python3
"""端到端冒烟测试：启动真实应用（含调度器），验证核心 API 与前端产物。

用法：python scripts/smoke_test.py
使用独立的临时 SQLite 数据库，不污染正式数据。
"""
import os
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

# 必须在导入 backend 前设置，保证 Settings/模型使用临时数据库
_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["REFRESH_INTERVAL_MINUTES"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from backend.api.main import app  # noqa: E402

failures = []


def check(name, cond, extra=""):
    if cond:
        print(f"[OK] {name}")
    else:
        print(f"[FAIL] {name} {extra}")
        failures.append(name)


with TestClient(app) as client:
    # 前端产物
    r = client.get("/")
    check("GET / 返回前端页面", r.status_code == 200 and "热点资讯" in r.text, r.status_code)

    # 未认证访问受保护接口应 401
    r = client.get("/api/config")
    check("未登录 GET /api/config 返回 401", r.status_code == 401, r.status_code)
    r = client.get("/api/scheduler")
    check("未登录 GET /api/scheduler 返回 401", r.status_code == 401, r.status_code)

    # 注册
    r = client.post("/api/register", json={"username": "smoke", "password": "smoke123"})
    check("POST /api/register 成功", r.status_code == 200 and r.json().get("success"), r.text[:120])
    token = r.json().get("token", "")
    headers = {"Authorization": f"Bearer {token}"}
    check("注册返回 token", bool(token))

    # 配置读写
    r = client.get("/api/config", headers=headers)
    check("GET /api/config 成功", r.status_code == 200 and r.json().get("success"), r.text[:120])
    r = client.post("/api/config", headers=headers, json={
        "platforms": ["weibo", "solidot"],
        "keywords": ["AI"],
        "push_enabled": False,
        "push_channel": "feishu",
        "push_webhook": "",
        "push_cron": "0 */4 * * *",
    })
    check("POST /api/config 保存成功", r.status_code == 200 and r.json().get("success"), r.text[:120])

    # 平台与新闻
    r = client.get("/api/platforms")
    check("GET /api/platforms 成功", r.status_code == 200 and r.json().get("success") and len(r.json()["platforms"]) >= 30, r.text[:120])
    r = client.get("/api/news/by_platform", headers=headers)
    check("GET /api/news/by_platform 成功", r.status_code == 200 and r.json().get("success"), r.text[:120])

    # 调度状态 API
    r = client.get("/api/scheduler", headers=headers)
    body = r.json()
    check("GET /api/scheduler 成功且运行中", r.status_code == 200 and body.get("success") and body.get("running") is True, r.text[:200])
    check("调度状态包含任务详情", "refresh_job" in body and "push_job" in body and "token_cleanup_job" in body)
    check("刷新间隔已读取", body.get("interval_minutes") == 1, body.get("interval_minutes"))

    r = client.post("/api/scheduler/interval", headers=headers, json={"minutes": 30})
    check("POST /api/scheduler/interval 成功", r.status_code == 200 and r.json().get("success"), r.text[:120])
    r = client.get("/api/scheduler", headers=headers)
    check("刷新间隔已更新为 30", r.json().get("interval_minutes") == 30, r.json().get("interval_minutes"))

    r = client.post("/api/scheduler/pause", headers=headers)
    check("POST /api/scheduler/pause 成功", r.status_code == 200 and r.json().get("success"), r.text[:120])
    r = client.get("/api/scheduler", headers=headers)
    check("暂停后 paused=True", r.json().get("paused") is True, r.text[:120])
    r = client.post("/api/scheduler/resume", headers=headers)
    check("POST /api/scheduler/resume 成功", r.status_code == 200 and r.json().get("success"), r.text[:120])
    r = client.get("/api/scheduler", headers=headers)
    check("恢复后 paused=False", r.json().get("paused") is False, r.text[:120])

    # 单平台刷新（solidot 为 RSS，已验证可访问）
    r = client.post("/api/news/refresh", headers=headers, params={"platform": "solidot"})
    body = r.json()
    check("POST /api/news/refresh(solidot) 成功", r.status_code == 200 and body.get("success") is True, r.text[:200])
    if body.get("sources"):
        status = body["sources"].get("solidot", {}).get("status")
        check("solidot 刷新状态非 missing", status is not None, status)

    # 推送未启用时应返回明确错误
    r = client.post("/api/push", headers=headers)
    check("POST /api/push 未启用返回错误", r.status_code == 200 and r.json().get("success") is False, r.text[:120])

    # 退出后 token 失效
    r = client.post("/api/logout", headers=headers)
    check("POST /api/logout 成功", r.status_code == 200, r.text[:120])
    r = client.get("/api/config", headers=headers)
    check("退出后旧 token 访问返回 401", r.status_code == 401, r.status_code)

print()
if failures:
    print(f"SMOKE FAILED: {len(failures)} 项未通过 -> {failures}")
    raise SystemExit(1)
print("SMOKE PASSED: 全部核心功能验证通过")
raise SystemExit(0)
