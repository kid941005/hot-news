#!/usr/bin/env python3
"""
Hot News Web - 热点资讯Web界面
"""

import os
import sys
import json
import secrets
import hashlib
from datetime import datetime
from functools import wraps

# Add scripts to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, jsonify, request, session
from flask_cors import CORS
import hot_news

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Secret key
app.secret_key = "hot-news-secret-2026"

# Data paths
DATA_DIR = os.path.expanduser("~/.openclaw/workspace/hot-news")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

os.makedirs(DATA_DIR, exist_ok=True)

# ============== User System ==============

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def load_config():
    default = {
        "keywords": [],
        "blocked_keywords": [],
        "push_enabled": False,
        "push_channel": "feishu",
        "push_webhook": "",
        "platforms": ["weibo", "baidu", "zhihu", "toutiao", "douyin", "bilibili"]
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return {**default, **json.load(f)}
    return default

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def get_user_config(user_id):
    users = load_users()
    if user_id in users:
        return users[user_id].get('config', load_config())
    return load_config()

def save_user_config(user_id, config):
    users = load_users()
    if user_id in users:
        users[user_id]['config'] = config
        save_users(users)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({"success": False, "error": "请先登录", "need_login": True})
        return f(*args, **kwargs)
    return decorated_function

# ============== Routes ==============

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/news')
def get_news():
    """获取热点新闻"""
    config = load_config()
    platforms = config.get('platforms', [])
    keywords = config.get('keywords', [])
    blocked = config.get('blocked_keywords', [])
    
    # 获取所有平台热点
    all_news = hot_news.fetch_all_hot(platforms if platforms else None)
    
    # 关键词过滤
    if keywords:
        all_news = hot_news.filter_by_keywords(all_news, keywords, blocked)
    elif blocked:
        all_news = hot_news.filter_by_keywords(all_news, None, blocked)
    
    return jsonify({
        "success": True,
        "news": all_news[:50],
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "platforms": config.get('platforms', [])
    })

@app.route('/api/config', methods=['GET', 'POST'])
@login_required
def manage_config():
    user_id = session.get('user_id')
    
    if request.method == 'GET':
        config = get_user_config(user_id)
        return jsonify({"success": True, "config": config})
    
    # POST - 更新配置
    data = request.json
    config = get_user_config(user_id)
    
    if 'keywords' in data:
        config['keywords'] = data['keywords']
    if 'blocked_keywords' in data:
        config['blocked_keywords'] = data['blocked_keywords']
    if 'platforms' in data:
        config['platforms'] = data['platforms']
    if 'push_enabled' in data:
        config['push_enabled'] = data['push_enabled']
    if 'push_channel' in data:
        config['push_channel'] = data['push_channel']
    if 'push_webhook' in data:
        config['push_webhook'] = data['push_webhook']
    
    save_user_config(user_id, config)
    
    return jsonify({"success": True, "message": "配置已保存"})

@app.route('/api/platforms')
def get_platforms():
    """获取可用平台列表"""
    return jsonify({
        "success": True,
        "platforms": [
            {"id": "weibo", "name": "微博", "icon": "🔵"},
            {"id": "baidu", "name": "百度", "icon": "🔴"},
            {"id": "zhihu", "name": "知乎", "icon": "🔵"},
            {"id": "toutiao", "name": "头条", "icon": "🔵"},
            {"id": "douyin", "name": "抖音", "icon": "🎵"},
            {"id": "bilibili", "name": "B站", "icon": "🔵"},
            {"id": "36kr", "name": "36Kr", "icon": "📊"},
            {"id": "jinri", "name": "今日头条", "icon": "📰"}
        ]
    })

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({"success": False, "error": "用户名和密码不能为空"})
    
    users = load_users()
    
    for uid, user in users.items():
        if user.get('username') == username:
            return jsonify({"success": False, "error": "用户名已存在"})
    
    user_id = hashlib.sha256(username.encode()).hexdigest()[:16]
    users[user_id] = {
        'username': username,
        'password': hashlib.sha256(password.encode()).hexdigest(),
        'config': load_config(),
        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_users(users)
    
    session['user_id'] = user_id
    session['username'] = username
    
    return jsonify({"success": True, "message": "注册成功", "username": username})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    users = load_users()
    
    user_id = None
    for uid, user in users.items():
        if user.get('username') == username:
            if user.get('password') == hashlib.sha256(password.encode()).hexdigest():
                user_id = uid
            break
    
    if not user_id:
        return jsonify({"success": False, "error": "用户名或密码错误"})
    
    session['user_id'] = user_id
    session['username'] = username
    
    return jsonify({"success": True, "message": "登录成功", "username": username})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "已退出登录"})

@app.route('/api/check-login', methods=['GET'])
def check_login():
    user_id = session.get('user_id')
    if user_id:
        return jsonify({"success": True, "logged_in": True, "username": session.get('username', '')})
    return jsonify({"success": True, "logged_in": False})

@app.route('/api/push', methods=['POST'])
@login_required
def push_news():
    """手动推送热点"""
    config = get_user_config(session.get('user_id'))
    
    if not config.get('push_enabled'):
        return jsonify({"success": False, "error": "推送未启用"})
    
    platforms = config.get('platforms', [])
    keywords = config.get('keywords', [])
    blocked = config.get('blocked_keywords', [])
    
    news = hot_news.fetch_all_hot(platforms if platforms else None)
    news = hot_news.filter_by_keywords(news, keywords, blocked)
    news = news[:10]
    
    # 生成内容
    content = f"📰 热点资讯 ({datetime.now().strftime('%H:%M')})\n\n"
    for i, item in enumerate(news, 1):
        content += f"{i}. {item['title']}\n"
    
    # 推送
    webhook = config.get('push_webhook', '')
    channel = config.get('push_channel', 'feishu')
    
    if channel == 'feishu':
        hot_news.push_to_feishu(webhook, content)
    else:
        hot_news.push_to_webhook(webhook, content)
    
    return jsonify({"success": True, "message": "推送成功"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
