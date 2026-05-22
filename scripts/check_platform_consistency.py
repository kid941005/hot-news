#!/usr/bin/env python3
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(root))

from backend.db.database import PLATFORM_MAP
from backend.spiders.spiders import SPIDERS

readme = (root / "README.md").read_text(encoding="utf-8")

section = readme.split("## 🖥️ 支持平台", 1)[1].split("##", 1)[0]
readme_platforms = []
for line in section.splitlines():
    match = re.match(r"\|\s*([^|\-][^|]*?)\s*\|\s*[^|]+\s*\|", line)
    if match and match.group(1).strip() != "平台":
        readme_platforms.append(match.group(1).strip())

map_names = list(PLATFORM_MAP.values())
errors = []
if readme_platforms != map_names:
    errors.append(f"README platforms != PLATFORM_MAP names: {readme_platforms} != {map_names}")

if set(PLATFORM_MAP) != set(SPIDERS):
    errors.append(f"PLATFORM_MAP keys != SPIDERS keys: {sorted(PLATFORM_MAP)} != {sorted(SPIDERS)}")

if errors:
    print("PLATFORM_CONSISTENCY_FAILED")
    for error in errors:
        print(error)
    raise SystemExit(1)

print(f"PLATFORM_CONSISTENCY_OK count={len(map_names)}")
