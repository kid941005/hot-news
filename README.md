# 🔥 Hot News - 热点资讯聚合平台

> 告别信息过载，聚合多平台热点，支持关键词筛选和消息推送

## 功能特性

- 📰 **多平台聚合** - 微博、百度、知乎、抖音、B站等热点
- 🔍 **关键词筛选** - 只看你关心的内容
- 🚫 **屏蔽词过滤** - 屏蔽不感兴趣的内容
- 📢 **消息推送** - 支持飞书、钉钉、Webhook推送
- 📱 **PWA支持** - 可添加到手机桌面
- 👤 **用户系统** - 独立配置，多用户支持

## 快速开始

### 1. 安装依赖

```bash
cd hot-news/web
pip install -r requirements.txt
```

### 2. 启动服务

```bash
python web/app.py
```

### 3. 访问

- 本地: http://localhost:5001
- 局域网: http://你的IP:5001

## 使用方法

1. 注册/登录账户
2. 选择感兴趣的平台
3. 设置关键词筛选（可选）
4. 配置推送渠道（可选）
5. 查看热点资讯

## 命令行工具

```bash
# 获取热点
python scripts/hot_news.py --fetch

# 关键词筛选
python scripts/hot_news.py --fetch --keywords 基金 理财

# 推送热点
python scripts/hot_news.py --push
```

## 配置说明

### 推送渠道

支持以下推送方式：
- 飞书Webhook
- 钉钉Webhook  
- 自定义WebHook

### 关键词语法

- 多个关键词用逗号分隔：如 `基金,A股,理财`
- 屏蔽词同样用逗号分隔

## 技术栈

- Python Flask
- JavaScript 原生
- PWA渐进式应用

## License

MIT
