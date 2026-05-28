# 🔥 热点资讯聚合平台

> 多平台热搜聚合 + 智能关键词过滤 + 个性化标签管理

中文

## ✨ 特性

- **多平台聚合**: 实时抓取 13 个主流平台热搜榜
- **智能过滤**: 支持按关键词精准过滤感兴趣的内容
- **标签管理**: 自定义多标签，每个标签独立配置关键词
- **用户系统**: 独立账号，数据按用户隔离
- **推送功能**: 支持飞书、钉钉 Webhook 推送
- **定时更新**: 后台自动刷新热点数据

## 🖥️ 支持平台

| 平台 | 状态 |
|------|------|
| 微博 | ✅ |
| 百度 | ✅ |
| B站 | ✅ |
| 抖音 | ⚠️ |
| 知乎 | ✅ |
| 头条 | ✅ |
| 华尔街见闻 | ✅ |
| 澎湃 | ✅ |
| 凤凰 | ✅ |
| 少数派 | ✅ |
| GitHub | ⚠️ |
| IT之家 | ✅ |
| 36Kr | ✅ |
| 腾讯新闻 | ✅ |
| 靠谱新闻 | ✅ |
| 参考消息 | ✅ |
| 虎扑 | ✅ |
| 百度贴吧 | ✅ |

> ⚠️ 部分平台因网络原因可能暂时不可用

## 🚀 快速开始

### 1. 安装依赖

```bash
# 后端依赖
pip install -r backend/requirements.txt

# 前端依赖
cd frontend
npm install
```

### 2. 启动服务

```bash
# 先构建前端（会自动同步到 backend/api/static）
cd frontend
npm install
npm run build
cd ..

# 启动后端
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 16888

# Docker
# docker compose up -d
```

### 3. 验证平台配置

```bash
python3 scripts/check_platform_consistency.py
```

### 4. 访问

- Web 界面: http://localhost:16888
- API 文档: http://localhost:16888/docs

## 📖 使用指南

### UI 界面预览

> 当前版本 UI 已升级为液态玻璃（Liquid Glass）视觉风格：深色渐变背景、半透明玻璃卡片、磨砂弹窗，以及统一的表单控件与滚动条细节。
>
> 建议在本地启动后补充最新截图到仓库（如 `docs/ui-home.png`、`docs/ui-account.png`），然后把下面占位说明替换成真实图片链接。
>
> 推荐截图位置：
> - 首页新闻列表
> - 标签筛选视图
> - 账号管理/推送设置弹窗

### 登录/注册

首次访问会自动跳转到登录页面，注册后即可使用完整功能。

### 配置关键词

1. 登录后点击右上角头像
2. 进入「关键词配置」
3. 为每个标签设置感兴趣的关键词（用逗号分隔）
4. 保存后自动按关键词过滤热点

### 标签管理

- 默认标签: 全部、工作、生活、科技
- 支持添加/删除/重命名自定义标签
- 每个标签独立配置关键词

### API 调用

```bash
# 登录获取 Token
curl -X POST http://localhost:16888/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"YOUR_USERNAME","password":"YOUR_PASSWORD"}'

# 获取热点（需认证）
curl http://localhost:16888/api/news \
  -H "Authorization: Bearer YOUR_TOKEN"

# 手动刷新热点（需认证）
curl -X POST http://localhost:16888/api/news/refresh \
  -H "Authorization: Bearer YOUR_TOKEN"


### MCP 服务

其他 Agent 可通过 MCP 调用热点数据。

stdio 启动：

```bash
python -m backend.mcp_server
```

Streamable HTTP 启动：

```bash
MCP_HOST=0.0.0.0 MCP_PORT=8000 python -m backend.mcp_server --transport streamable-http
```

HTTP MCP 地址：`http://localhost:8000/mcp`。

Hermes Agent stdio 示例：

```yaml
mcp_servers:
  hot_news:
    command: "python"
    args: ["-m", "backend.mcp_server"]
    env:
      DATABASE_URL: "sqlite:////app/backend/hot_news.db"
```

Hermes Agent HTTP 示例：

```yaml
mcp_servers:
  hot_news:
    url: "http://127.0.0.1:8000/mcp"
```

提供工具：`list_platforms`、`get_latest_news`、`search_news`、`get_news_by_platform`。

## 📁 项目结构

```
hot-news/
├── backend/              # FastAPI 后端
│   ├── api/
│   │   ├── main.py       # API 入口
│   │   └── static/       # 已构建前端静态文件
│   ├── db/
│   │   └── database.py   # 数据库操作
│   ├── models/
│   │   └── models.py     # 数据模型
│   ├── spiders/
│   │   └── spiders.py    # 爬虫模块
│   ├── mcp_server.py     # MCP stdio 服务入口
│   └── requirements.txt  # 后端依赖
├── frontend/             # Vue3 前端源码
│   ├── src/
│   │   ├── App.vue       # 主组件
│   │   └── main.js       # 入口文件
│   └── vite.config.js
├── web/                  # Flask 旧版 Web（兼容）
├── scripts/              # 工具脚本
│   └── check_platform_consistency.py  # 平台一致性校验
├── hot_news.py           # 旧版脚本入口
├── Dockerfile            # Docker 镜像构建配置
├── docker-compose.yml    # Docker 编排配置
```

## ⚙️ 配置

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | 数据库连接 | `sqlite:///./hot_news.db` |
| `REFRESH_INTERVAL_MINUTES` | 独立定时刷新新闻的间隔分钟数 | `15` |
| `PUSH_INTERVAL_HOURS` | 推送间隔小时数（兼容旧配置） | `4` |
| `MCP_HOST` | Streamable HTTP MCP 监听地址 | `127.0.0.1` |
| `MCP_PORT` | Streamable HTTP MCP 监听端口 | `8000` |
| `MCP_PATH` | Streamable HTTP MCP 路径 | `/mcp` |
| `MCP_TRANSPORT` | MCP 默认传输方式，支持 `stdio` / `streamable-http` | `stdio` |

### 推送配置

在用户配置中设置 Webhook 地址：
- 飞书: `https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_TOKEN`
- 钉钉: `https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN`
- Bark: `https://api.day.app/YOUR_KEY`

## 🛠️ 部署

### Docker 部署

```bash
docker compose up -d
```

当前仓库只保留这一份主 `docker-compose.yml`。
`JWT_SECRET` 已直接写在 compose 配置中，因此无需额外再准备 `.env`。

### 生产环境

建议使用 Nginx 反向代理 + HTTPS

## 📝 更新日志

### v2.5.21 (2026-05-28)
- 新增：提供 Hot News MCP 服务，支持其他 Agent 读取热点数据
- 新增：支持 stdio 与 Streamable HTTP 两种 MCP 启动方式
- 文档：补充 MCP 启动、HTTP 地址和 Hermes Agent 配置示例

### v2.5.20 (2026-05-28)
- 优化：底部展示当前版本号，便于确认运行版本
- 优化：`全部` 页从 `xl` 屏幕起使用三列布局，提升桌面空间利用率
- 优化：`全部` 页不再限制每个信息源返回条数，展示数据库内该渠道全部新闻

### v2.5.19 (2026-05-28)
- 清理：移除已下线的 V2EX、金十数据爬虫残留代码
- 清理：删除未使用的刷新状态辅助函数和 Docker 镜像中的旧入口复制
- 验收：后端编译、平台一致性、pytest、前端构建、Docker 构建和关键 API 均通过

### v2.5.18 (2026-05-28)
- 新增：补充腾讯新闻、靠谱新闻、参考消息、虎扑、百度贴吧 5 个资讯来源
- 优化：手动刷新接口返回各平台抓取状态，便于排查失败或空数据来源
- 修复：刷新时间在服务重启后可从数据库最新更新时间回退展示，避免误判定时刷新未执行
- 优化：`全部` 标签页不再重复显示条目后的信息源徽标

### v2.5.17 (2026-05-28)
- 修复：前端构建脚本先创建 `backend/api/static` 目录，避免 Docker workflow 构建阶段因目录不存在失败

### v2.5.16 (2026-05-25)
- 优化：主界面从窄栏扩展为更适合桌面的多列平台卡片布局，降低信息拥挤感
- 优化：平台卡片与新闻条目补充平台标识、序号层级与更新时间展示，提升可读性
- 运维：Compose 部署收口为单一 `docker-compose.yml`，移除过时 `version` 字段，并同步 README 部署说明

### v2.5.15 (2026-05-24)
- 修复：本地前端构建后自动同步静态资源到 `backend/api/static`，避免首页引用旧 hash 资源导致空白页
- 修复：补齐本地启动文档，明确先构建前端再启动后端，避免静态资源与首页不一致
- 发布：同步新的 `backend/api/static` 构建产物，清理旧版静态资源文件

### v2.5.14 (2026-05-24)
- 修复：消息推送按用户关键词配置筛选，兼容数据库中 JSON 字符串形式的 `keywords`、`blocked_keywords`、`keyword_tags`
- 修复：取消推送消息只取最新 10 条的硬限制，避免符合条件的新闻被截断
- 验收：补充后端 API 最小链路验收，确认登录、配置、新闻筛选与推送校验分支可用

### v2.5.13 (2026-05-24)
- 修复：IT之家发布时间晚 8 小时的问题，按正确时区解析 RSS `pubDate`
- 修复：B站、知乎、头条、36Kr 的发布时间统一改为按 UTC 时间戳正确转换，避免重复 `+8小时`
- 优化：前端补齐横屏、竖屏、异形屏的最小屏幕适配，改善窄屏卡片与弹窗显示

### v2.5.12 (2026-05-23)
- 新增：独立定时刷新任务，后台默认每 15 分钟自动抓取一次新闻，不依赖推送配置
- 保持：定时推送仍每分钟检查 cron，到点后再执行推送
- 配置：新增 `REFRESH_INTERVAL_MINUTES` 环境变量用于控制定时刷新频率

### v2.5.11 (2026-05-23)
- 修复：手动刷新接口在异步 FastAPI 请求中不再错误调用 `asyncio.run()`，避免刷新时报 `running event loop`
- 修复：数据库 schema 兼容逻辑补充 SQLite，对 `user_configs.push_cron` 缺列场景自动补齐
- 修复：无稳定发布时间的平台继续按抓取时间展示，便于部署后通过刷新覆盖旧脏数据

### v2.5.10 (2026-05-23)
- 优化：继续提升首页产品感，强化筛选栏、分组头和空状态的信息层级
- 优化：账号管理弹窗统一为亮色液态玻璃风格，细化标签设置、屏蔽关键词、监控平台与推送设置的可读性

### v2.5.9 (2026-05-23)
- 修复：统一新闻时间语义，区分“发布时间”和“获取时间”展示
- 修复：知乎、头条、IT之家、36Kr 等来源的时间解析，避免依赖服务器时区
- 修复：微博、百度、华尔街见闻...[truncated]

### v2.5.8 (2026-05-23)
- 优化：整体界面降低白亮感，背景改为更克制的灰蓝渐变过渡
- 优化：header、操作栏与卡片收敛高光，增强冷灰蓝层次和立体感

### v2.5.7 (2026-05-23)
- 修复：亮色玻璃主题下白底白字导致的可读性问题，恢复深色高对比文本
- 修复：标签页与普通列表中的来源平台徽标恢复按平台区分彩色样式

### v2.5.5 (2026-05-23)
- 优化：前端界面升级为液态玻璃视觉风格，统一深色玻璃背景、卡片、按钮与弹窗样式
- 优化：继续精修账号管理、标签编辑、推送设置等主要操作区的玻璃态视觉细节
- 优化：统一输入框、下拉框、复选框和滚动条等控件的玻璃态交互细节

### v2.5.4 (2026-05-23)
- 修复：手动推送前先刷新最新新闻数据，再执行推送
- 修复：定时推送命中 cron 后先刷新最新新闻数据，再执行推送
- 移除：彻底删除金十数据和 V2EX 渠道支持，平台总数同步为 13

### v2.5.1 (2026-05-23)
- 修复：MySQL 旧库缺少 push_cron 列导致定时推送和新闻接口 500
- 修复：启动时自动补齐 user_configs.push_cron 兼容旧数据库

### v2.5.0 (2026-06-10)
- 新增：定时推送调度器（APScheduler），按 cron 表达式自动推送
- 新增：Web 界面支持自定义推送规则（预设 7 种 + 自定义 cron）
- 新增：每个用户独立配置推送间隔和上次推送时间展示
- 新增：全局调度器每分钟检查所有用户的 cron 表达式

### v2.4.0 (2026-06-10)
- 新增：钉钉推送支持按标签分组，标题可点击跳转
- 新增：飞书推送升级为 Markdown 格式，支持超链接
- 新增：Bark (iOS) 推送升级为 Markdown 格式，支持超链接
- 修复：所有渠道推送内容统一按标签分组展示

### v2.3.0 (2026-06-10)
- 新增：Bark (iOS) 推送通知支持
- 新增：关键词输入支持中文逗号/分号混合分隔符
- 新增：全角逗号、全角分号自动识别为关键词分隔符

### v2.2.0 (2026-06-10)
- 修复："全部"标签页缺少认证头导致无法按用户平台筛选
- 修复：keyword_tags 空字典被当成 falsy 导致标签关键词不生效
- 修复：空 filter_keywords 错误回退到全局关键词
- 修复：Docker 容器时区 UTC 导致刷新时间显示错误
- 修复：Docker 镜像自动推送到 Docker Hub + ghcr.io
- 修复：docker-compose.yml 使用预构建镜像，开箱即用

### v1.0
- 初始版本 Flask + 简单前端

## 🤝 贡献

欢迎提交 Issue 和 PR！

## 📄 许可证

MIT License
