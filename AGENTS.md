# hot-news 项目指南

## 项目概述

FastAPI + Vue3 + MySQL 的新闻聚合器，Docker 部署，支持 18 个新闻平台抓取。

## 项目结构

```
hot-news/
├── backend/
│   ├── api/main.py       # FastAPI 主入口（API + MCP 集成）
│   ├── spiders/spiders.py # 18 个平台爬虫
│   ├── db/database.py    # 数据库操作
│   ├── models/models.py  # ORM 模型
│   └── mcp_server.py     # MCP 服务入口
├── frontend/
│   └── src/App.vue       # Vue3 SPA 主界面
├── legacy/               # 旧实现归档（已不参与部署）
├── docker-compose.yml    # 部署配置
├── Dockerfile            # 镜像构建
└── scripts/
    ├── check_platform_consistency.py
    └── verify_security_scan.py
```

## 开发约定

### 前端构建
- 使用 `corepack npm`（非裸 `npm`）
- 每次修改后跑 `cd frontend && corepack npm run build`
- UI 风格：浅色灰蓝玻璃质感，**不要改为深色主题**

### 后端
- Python 3.11+
- 使用 SQLAlchemy ORM
- 新功能只改 `backend/` 主链路，不改 `legacy/`

### 测试与验证
每次变更后必须运行：
```bash
python3 -m compileall -q backend tests scripts
python3 -m pytest -q
python3 scripts/verify_security_scan.py
python3 scripts/check_platform_consistency.py
cd frontend && corepack npm run build
docker compose -f docker-compose.yml config >/dev/null
git diff --check
```

### Git
- 用户：kid941005
- 提交格式：常规提交（feat/fix/docs/chore/refactor）
- 优先使用 `gh` CLI 处理 GitHub 操作
- 发布流程：提升 version → README 日志 → 构建 → commit → tag → push → `gh release create`

### 发布版本
- 版本记录在 `frontend/package.json` 和 `backend/api/main.py`
- 每次发布同步更新 `README.md` 更新日志
- 版本号递增小版本（2.5.x）

### 部署
- Docker Compose 部署，镜像发到 Docker Hub 和 GHCR
- compose 包含 Web 服务 + MySQL + 独立 MCP 服务
- 数据库连接：`${MYSQL_ROOT_PASSWORD:-hotnews123}`

## 自动刷新机制
- 页面请求时自动触发后台抓取（30 秒冷却）
- 数据库为空时同步等待刷新
- 设置 `AUTO_REFRESH_COOLDOWN_SECONDS` 环境变量可调整冷却

## 渠道
共 18 个新闻平台，定义在 `backend/spiders/spiders.py` 和 `backend/db/database.py` 的 PLATFORM_MAP 中。
