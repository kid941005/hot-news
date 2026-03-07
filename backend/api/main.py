#!/usr/bin/env python3
"""
FastAPI 应用 - 带Vue3前端
"""
import os
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session

from backend.models.models import init_db, get_db, UserConfig
from backend.db import database
from backend.spiders import spiders

app = FastAPI(title="热点资讯", version="2.0")

# 静态文件路径
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============= 数据模型 =============

class LoginRequest(BaseModel):
    username: str
    password: str


class ConfigRequest(BaseModel):
    keywords: Optional[List[str]] = None
    blocked_keywords: Optional[List[str]] = None
    keyword_tags: Optional[dict] = None  # 关键词标签映射
    platforms: Optional[List[str]] = None


# ============= 依赖 =============

# Token 认证
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict

# 简单的 token 存储 (生产环境应该用数据库或 Redis)
_tokens: Dict[str, tuple] = {}  # {token: (user_id, expires_at)}

def generate_token(user_id: int, expires_hours: int = 24 * 7) -> str:
    """生成 token"""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=expires_hours)
    _tokens[token] = (user_id, expires_at)
    return token

def verify_token(token: str) -> Optional[int]:
    """验证 token，返回 user_id"""
    if not token or token not in _tokens:
        return None
    user_id, expires_at = _tokens[token]
    if datetime.now() > expires_at:
        del _tokens[token]
        return None
    return user_id

def delete_token(token: str):
    """删除 token"""
    if token in _tokens:
        del _tokens[token]

def get_current_user_id(Authorization: Optional[str] = Header(None)) -> int:
    """获取当前用户ID - 从 Authorization header 获取 token"""
    # 尝试从 header 获取 token
    if Authorization and Authorization.startswith("Bearer "):
        token = Authorization[7:]  # 去掉 "Bearer " 前缀
        user_id = verify_token(token)
        if user_id:
            return user_id
    return 1  # 默认返回用户1


# ============= 前端页面 =============

HTML_PAGE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>热点资讯</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif; background: #f5f5f7; color: #1a1a2e; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 16px; color: white; position: sticky; top: 0; z-index: 100; }
        .header h1 { font-size: 18px; font-weight: 600; }
        .user-btn { float: right; padding: 6px 14px; background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3); border-radius: 16px; color: white; font-size: 13px; cursor: pointer; }
        .main { max-width: 600px; margin: 0 auto; padding: 16px; }
        .toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
        .count { color: #666; font-size: 14px; }
        .refresh-btn { padding: 8px 16px; background: #667eea; color: white; border: none; border-radius: 8px; font-size: 14px; cursor: pointer; }
        .news-item { background: white; padding: 14px; margin-bottom: 12px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
        .news-title { font-size: 15px; font-weight: 500; color: #1a1a2e; text-decoration: none; }
        .news-title:hover { color: #667eea; }
        .news-platform { display: inline-block; font-size: 11px; padding: 2px 8px; border-radius: 10px; margin-left: 8px; }
        .weibo { background: #ffefe0; color: #e6162d; }
        .baidu { background: #e3f1fd; color: #2932e1; }
        .bilibili { background: #fceef5; color: #fb7299; }
        .douyin { background: #fff5e6; color: #ff6b00; }
        .modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.5); align-items: center; justify-content: center; z-index: 200; }
        .modal.show { display: flex; }
        .modal-content { background: white; padding: 24px; border-radius: 16px; width: 90%; max-width: 360px; }
        .modal h2 { font-size: 18px; margin-bottom: 16px; }
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; font-size: 13px; color: #666; margin-bottom: 6px; }
        .form-group input, .form-group textarea { width: 100%; padding: 10px; border: 1px solid #e8e8e8; border-radius: 10px; font-size: 14px; }
        .form-group textarea { resize: vertical; min-height: 60px; }
        .checkbox-group { display: flex; flex-wrap: wrap; gap: 8px; }
        .checkbox-group label { background: #f5f5f7; padding: 6px 12px; border-radius: 16px; font-size: 13px; }
        .btn { width: 100%; padding: 12px; border: none; border-radius: 10px; font-size: 15px; cursor: pointer; margin-bottom: 8px; }
        .btn-primary { background: #667eea; color: white; }
        .btn-secondary { background: #f5f5f7; color: #666; }
        .btn-danger { background: #ef4444; color: white; }
        .btn-group { display: flex; gap: 8px; flex-wrap: wrap; }
        .btn-group .btn { flex: 1; min-width: 80px; }
        .tag-selector { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0; }
        .tag-btn { padding: 6px 12px; border: none; border-radius: 16px; font-size: 13px; cursor: pointer; }
        .tag-hint { font-size: 12px; color: #999; margin: 4px 0; }
        .keyword-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
        .keyword-tag { padding: 4px 10px; border-radius: 12px; font-size: 12px; color: white; }
        .empty { text-align: center; padding: 40px; color: #999; }
    </style>
</head>
<body>
    <header class="header">
        <h1>热点资讯</h1>
        <button class="user-btn" id="userBtn" onclick="showLogin()">登录</button>
    </header>
    <main class="main">
        <div class="toolbar">
            <span class="count" id="count">0 条匹配</span>
            <button class="refresh-btn" onclick="refreshCache()">刷新</button>
        </div>
        <div id="newsList"></div>
    </main>

    <!-- 登录/注册弹窗 -->
    <div class="modal" id="loginModal">
        <div class="modal-content">
            <h2>登录 / 注册</h2>
            <div class="form-group">
                <input type="text" id="username" placeholder="用户名">
            </div>
            <div class="form-group">
                <input type="password" id="password" placeholder="密码">
            </div>
            <button class="btn btn-primary" onclick="login()">登录</button>
            <button class="btn btn-secondary" onclick="register()">注册</button>
            <button class="btn btn-secondary" onclick="hideLogin()">取消</button>
        </div>
    </div>

    <!-- 账号管理弹窗 -->
    <div class="modal" id="accountModal">
        <div class="modal-content">
            <h2>账号管理</h2>
            <div class="form-group">
                <label>关注关键词（逗号分隔）</label>
                <textarea id="keywordsInput" placeholder="如: 小米,比亚迪,华为"></textarea>
                <div class="keyword-tags" id="keywordTags"></div>
            </div>
            <div class="form-group">
                <label>关键词标签</label>
                <div class="tag-selector">
                    <button class="tag-btn" data-tag="工作" style="background:#3b82f6;color:white" onclick="applyTag('工作')">工作</button>
                    <button class="tag-btn" data-tag="日常" style="background:#10b981;color:white" onclick="applyTag('日常')">日常</button>
                    <button class="tag-btn" data-tag="科技" style="background:#8b5cf6;color:white" onclick="applyTag('科技')">科技</button>
                    <button class="tag-btn" data-tag="投资" style="background:#f59e0b;color:white" onclick="applyTag('投资')">投资</button>
                    <button class="tag-btn" data-tag="自定义" style="background:#6b7280;color:white" onclick="applyCustomTag()">自定义</button>
                </div>
                <p class="tag-hint">选择关键词后点击标签即可标记</p>
            </div>
            <div class="form-group">
                <label>屏蔽关键词</label>
                <textarea id="blockedInput" placeholder="不想看到的内容"></textarea>
            </div>
            <div class="form-group">
                <label>监控平台</label>
                <div class="checkbox-group">
                    <label><input type="checkbox" value="weibo"> 微博</label>
                    <label><input type="checkbox" value="baidu"> 百度</label>
                    <label><input type="checkbox" value="douyin"> 抖音</label>
                    <label><input type="checkbox" value="bilibili"> B站</label>
                    <label><input type="checkbox" value="zhihu"> 知乎</label>
                    <label><input type="checkbox" value="toutiao"> 头条</label>
                    <label><input type="checkbox" value="36kr"> 36Kr</label>
                    <label><input type="checkbox" value="ithome"> IT之家</label>
                    <label><input type="checkbox" value="sspai"> 少数派</label>
                    <label><input type="checkbox" value="v2ex"> V2EX</label>
                </div>
            </div>
            <div class="btn-group">
                <button class="btn btn-primary" onclick="saveConfig()">保存</button>
                <button class="btn btn-secondary" onclick="switchAccount()">切换账号</button>
                <button class="btn btn-danger" onclick="logout()">退出登录</button>
                <button class="btn btn-secondary" onclick="hideAccount()">关闭</button>
            </div>
        </div>
    </div>

    <script>
        let currentUser = localStorage.getItem('username') || null;
        let authToken = localStorage.getItem('token') || null;
        
        // 获取认证头
        function getAuthHeader() {
            return authToken ? { 'Authorization': 'Bearer ' + authToken } : {};
        }
        
        // 页面加载时恢复登录状态
        document.addEventListener('DOMContentLoaded', () => {
            if (currentUser) {
                document.getElementById('userBtn').textContent = currentUser;
                document.getElementById('userBtn').onclick = showAccount;
            }
            loadNews();
        });
        
        async function refreshCache() {
            const btn = document.querySelector('.refresh-btn');
            btn.textContent = '刷新中...';
            try {
                await fetch('/api/news/refresh', {
                    method: 'POST',
                    headers: getAuthHeader()
                });
                await loadNews();
            } catch(e) {}
            btn.textContent = '刷新';
        }
        
        async function loadNews() {
            const r = await fetch('/api/news', { headers: getAuthHeader() });
            const d = await r.json();
            document.getElementById('count').textContent = d.total + ' 条匹配';
            
            const list = document.getElementById('newsList');
            if (d.news.length === 0) {
                list.innerHTML = '<div class="empty">暂无匹配的热点资讯</div>';
                return;
            }
            
            list.innerHTML = d.news.map(n => {
                const platformClass = n.platform === '微博' ? 'weibo' : n.platform === '百度' ? 'baidu' : n.platform === 'B站' ? 'bilibili' : 'douyin';
                return '<div class="news-item"><a class="news-title" href="' + n.url + '" target="_blank">' + n.title + '</a><span class="news-platform ' + platformClass + '">' + n.platform + '</span></div>';
            }).join('');
        }
        
        async function loadConfig() {
            const r = await fetch('/api/config', { headers: getAuthHeader() });
            const d = await r.json();
            if (d.success && d.config) {
                document.getElementById('keywordsInput').value = (d.config.keywords || []).join(', ');
                document.getElementById('blockedInput').value = (d.config.blocked_keywords || []).join(', ');
                document.querySelectorAll('#accountModal input[type="checkbox"]').forEach(cb => {
                    cb.checked = (d.config.platforms || []).includes(cb.value);
                });
                // 加载关键词标签
                window.keywordTags = d.config.keyword_tags || {};
                renderKeywordTags();
            }
        }
        
        function renderKeywordTags() {
            const container = document.getElementById('keywordTags');
            const keywords = document.getElementById('keywordsInput').value.split(',').map(s => s.trim()).filter(s => s);
            const tagColors = {
                '工作': '#3b82f6', '日常': '#10b981', '科技': '#8b5cf6',
                '投资': '#f59e0b', '自定义': '#6b7280'
            };
            container.innerHTML = keywords.map(kw => {
                const tag = window.keywordTags?.[kw] || '';
                const color = tagColors[tag] || '#6b7280';
                return tag ? `<span class="keyword-tag" style="background:${color}">${kw} · ${tag}</span>` : '';
            }).join('');
        }
        
        function applyTag(tagName) {
            const input = document.getElementById('keywordsInput');
            const keywords = input.value.split(',').map(s => s.trim()).filter(s => s);
            if (keywords.length === 0) {
                alert('请先输入关键词');
                return;
            }
            // 为最后一个关键词添加标签
            const lastKeyword = keywords[keywords.length - 1];
            window.keywordTags = window.keywordTags || {};
            window.keywordTags[lastKeyword] = tagName;
            renderKeywordTags();
            alert(`已为 "${lastKeyword}" 添加标签: ${tagName}`);
        }
        
        function applyCustomTag() {
            const customTag = prompt('请输入自定义标签名称:');
            if (customTag && customTag.trim()) {
                applyTag(customTag.trim());
            }
        }
        
        function switchAccount() {
            logout();
            showLogin();
        }
        
        async function login() {
            const r = await fetch('/api/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    username: document.getElementById('username').value,
                    password: document.getElementById('password').value
                })
            });
            const d = await r.json();
            if (d.success) {
                currentUser = d.username;
                authToken = d.token;
                localStorage.setItem('username', d.username);
                localStorage.setItem('token', d.token);
                document.getElementById('userBtn').textContent = d.username;
                document.getElementById('userBtn').onclick = showAccount;
                hideLogin();
                loadConfig();
                loadNews();
            } else {
                alert(d.error || '登录失败');
            }
        }
        
        async function register() {
            const r = await fetch('/api/register', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    username: document.getElementById('username').value,
                    password: document.getElementById('password').value
                })
            });
            const d = await r.json();
            if (d.success) {
                currentUser = d.username;
                authToken = d.token;
                localStorage.setItem('username', d.username);
                localStorage.setItem('token', d.token);
                document.getElementById('userBtn').textContent = d.username;
                document.getElementById('userBtn').onclick = showAccount;
                hideLogin();
                loadConfig();
                loadNews();
            } else {
                alert(d.error || '注册失败');
            }
        }
        
        async function saveConfig() {
            try {
                const keywordsInput = document.getElementById('keywordsInput');
                const blockedInput = document.getElementById('blockedInput');
                
                if (!keywordsInput || !blockedInput) {
                    alert('页面加载错误，请刷新重试');
                    return;
                }
                
                const keywords = keywordsInput.value.split(',').map(s => s.trim()).filter(s => s);
                const blocked = blockedInput.value.split(',').map(s => s.trim()).filter(s => s);
                const platforms = [];
                document.querySelectorAll('#accountModal input[type="checkbox"]:checked').forEach(cb => platforms.push(cb.value));
                
                const payload = { 
                    keywords: keywords, 
                    blocked_keywords: blocked, 
                    platforms: platforms 
                };
                
                console.log('发送数据:', JSON.stringify(payload));
                
                const res = await fetch('/api/config', {
                    method: 'POST',
                    headers: { ...getAuthHeader(), 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                
                console.log('响应状态:', res.status);
                const text = await res.text();
                console.log('响应内容:', text);
                
                if (!res.ok) {
                    alert('保存失败: HTTP ' + res.status);
                    return;
                }
                
                const d = JSON.parse(text);
                if (d.success) {
                    alert('保存成功！关键词: ' + keywords.join(', '));
                    hideAccount();
                    loadNews();
                } else {
                    alert('保存失败: ' + (d.error || '未知错误'));
                }
            } catch(e) {
                alert('保存失败: ' + e.message);
            }
        }
        
        async function logout() {
            await fetch('/api/logout', { 
                method: 'POST',
                headers: { 'Authorization': 'Bearer ' + authToken }
            });
            currentUser = null;
            authToken = null;
            localStorage.removeItem('username');
            localStorage.removeItem('token');
            document.getElementById('userBtn').textContent = '登录';
            document.getElementById('userBtn').onclick = showLogin;
            hideAccount();
            loadNews();
        }
        
        function showLogin() { document.getElementById('loginModal').classList.add('show'); }
        function hideLogin() { document.getElementById('loginModal').classList.remove('show'); }
        function showAccount() { loadConfig(); document.getElementById('accountModal').classList.add('show'); }
        function hideAccount() { document.getElementById('accountModal').classList.remove('show'); }
        
        loadNews();
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTML_PAGE


# ============= API接口 =============

@app.post("/api/register")
def register(req: LoginRequest, db: Session = Depends(get_db)):
    try:
        user = database.create_user(db, req.username, req.password)
        token = generate_token(user.id)
        return {"success": True, "username": user.username, "user_id": user.id, "token": token}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = database.verify_user(db, req.username, req.password)
    if user:
        token = generate_token(user.id)
        return {"success": True, "username": user.username, "user_id": user.id, "token": token}
    return {"success": False, "error": "用户名或密码错误"}


@app.post("/api/logout")
def logout(Authorization: Optional[str] = None):
    if Authorization and Authorization.startswith("Bearer "):
        token = Authorization[7:]
        delete_token(token)
    return {"success": True}


@app.get("/api/config")
def get_config(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    config = database.get_user_config(db, user_id)
    if not config:
        return {"success": True, "config": {}}
    return {
        "success": True,
        "config": {
            "keywords": config.keywords or [],
            "blocked_keywords": config.blocked_keywords or [],
            "keyword_tags": config.keyword_tags or {},
            "platforms": config.platforms or [],
        }
    }


@app.get("/api/tags")
def get_tags(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """获取用户的标签列表"""
    config = database.get_user_config(db, user_id)
    if not config or not config.keyword_tags:
        # 返回默认标签（仅当没有任何配置时）
        return {
            "success": True,
            "tags": ["工作", "生活", "科技"],
            "keyword_tags": {}
        }
    
    import json
    keyword_tags = config.keyword_tags
    if isinstance(keyword_tags, str):
        keyword_tags = json.loads(keyword_tags)
    
    # 提取所有标签（用户删除的标签不再显示）
    all_tags = list(keyword_tags.keys())
    
    # 按默认顺序排序（工作、生活、科技、其他）
    default_order = ["工作", "生活", "科技"]
    sorted_tags = []
    for tag in default_order:
        if tag in all_tags:
            sorted_tags.append(tag)
    for tag in all_tags:
        if tag not in default_order:
            sorted_tags.append(tag)
    
    return {
        "success": True,
        "tags": sorted_tags,
        "keyword_tags": keyword_tags
    }


@app.post("/api/config")
def update_config(req: ConfigRequest, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    config_data = req.dict(exclude_unset=True)
    database.update_user_config(db, user_id, config_data)
    return {"success": True}


@app.get("/api/news")
def get_news(
    tag: str = None,  # 标签筛选
    today: bool = True,  # 只显示当天发布的文章
    all: bool = False,  # 获取所有热榜，不按关键词过滤
    user_id: int = Depends(get_current_user_id), 
    db: Session = Depends(get_db)
):
    config = db.query(UserConfig).filter(UserConfig.user_id == user_id).first()
    
    # 如果指定了all=true，获取所有热榜（不按关键词过滤）
    if all:
        news_list = database.get_all_news(db)
        matched_keywords = {}
    elif tag and config and config.keyword_tags:
        # 如果指定了标签，使用该标签的关键词
        import json
        if isinstance(config.keyword_tags, str):
            keyword_tags = json.loads(config.keyword_tags)
        else:
            keyword_tags = config.keyword_tags
        
        # 直接获取该标签对应的关键词列表
        filter_keywords = keyword_tags.get(tag, [])
        news_list, matched_keywords = database.get_user_filtered_news(db, user_id, filter_keywords)
    else:
        # 默认按用户关键词过滤
        news_list, matched_keywords = database.get_user_filtered_news(db, user_id)
    
    # 过滤当天发布的文章并按时间倒序
    today_str = datetime.now().strftime("%Y-%m-%d")
    news_data = []
    for n in news_list:
        # 检查是否是当天发布的
        if today and n.created_at:
            if n.created_at.strftime("%Y-%m-%d") != today_str:
                continue
        
        item = n.to_dict()
        # 标记匹配的关键词
        item['matched_keywords'] = matched_keywords.get(n.id, [])
        news_data.append(item)
    
    # 按时间倒序排列
    news_data.sort(key=lambda x: x.get('pub_time', ''), reverse=True)
    
    return {
        "success": True,
        "news": news_data,
        "total": len(news_data),
        "current_tag": tag
    }


from datetime import datetime

# 存储刷新时间
LAST_REFRESH_TIME = None

@app.post("/api/news/refresh")
async def refresh_news(db: Session = Depends(get_db)):
    global LAST_REFRESH_TIME
    results = await spiders.fetch_all_spiders()
    for platform, news in results.items():
        if news:
            database.save_news(db, news)
    LAST_REFRESH_TIME = datetime.now()
    return {"success": True, "last_refresh": LAST_REFRESH_TIME.isoformat()}


@app.get("/api/news/refresh")
def get_refresh_time():
    global LAST_REFRESH_TIME
    if LAST_REFRESH_TIME:
        return {
            "success": True,
            "last_refresh": LAST_REFRESH_TIME.isoformat(),
            "display": LAST_REFRESH_TIME.strftime("%H:%M")
        }
    return {"success": True, "last_refresh": None}


@app.on_event("startup")
def startup():
    init_db()
    # 挂载静态文件
    if os.path.exists(STATIC_DIR):
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=16888)
