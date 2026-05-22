# 🔥 热点资讯聚合平台

> 多平台热搜聚合 + 智能关键词过滤 + 个性化标签管理

中文

## ✨ 特性

- **多平台聚合**: 实时抓取 15 个主流平台热搜榜
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
| V2EX | ⚠️ |
| GitHub | ⚠️ |
| 金十数据 | ⚠️ |
| IT之家 | ✅ |
| 36Kr | ✅ |

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
# 方式一: 直接运行
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 16888

# Docker

docker compose up -d
```

### 3. 验证平台配置

```bash
python3 scripts/check_platform_consistency.py
```

### 4. 访问

- Web 界面: http://localhost:16888
- API 文档: http://localhost:16888/docs

## 📖 使用指南

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
```

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

### 推送配置

在用户配置中设置 Webhook 地址：
- 飞书: `https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_TOKEN`
- 钉钉: `https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN`

## 🛠️ 部署

### Docker 部署

```bash
docker compose up -d
```

### 生产环境

建议使用 Nginx 反向代理 + HTTPS

## 📝 更新日志

### v2.1.0 (2026-05-22)
- 全新 Vue3 + FastAPI 架构
- 后端定时任务
- 数据缓存机制
- 新增 Dockerfile、.dockerignore 与 GitHub Actions Docker 构建 workflow
- 平台配置一致性校验脚本

### v1.0
- 初始版本 Flask + 简单前端

## 🤝 贡献

欢迎提交 Issue 和 PR！

## 📄 许可证

MIT License
