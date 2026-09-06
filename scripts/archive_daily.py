#!/usr/bin/env python3
"""每日热点归档：抓取全平台热榜并写入 archive/YYYY-MM-DD.json。

对标 douyin-hot-hub 的 GitHub Actions 定时归档方案：
- 零服务器成本，由 GitHub Actions cron 每天执行；
- 快照按日期落盘，提交到仓库留档，便于事后追溯。
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.spiders import spiders

BEIJING_TZ = timezone(timedelta(hours=8))


def main() -> int:
    results = asyncio.run(spiders.fetch_all_spiders())
    now = datetime.now(BEIJING_TZ)
    archive_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "archive")
    os.makedirs(archive_dir, exist_ok=True)
    path = os.path.join(archive_dir, f"{now.strftime('%Y-%m-%d')}.json")

    payload = {
        "date": now.strftime("%Y-%m-%d"),
        "generated_at": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "platforms": results,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    total = sum(len(items) for items in results.values())
    print(f"[OK] 归档完成: {path}（{total} 条）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
