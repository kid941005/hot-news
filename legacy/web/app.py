#!/usr/bin/env python3
"""
Hot News Web - 热点资讯Web界面
"""

import os
import sys
import json
import hashlib
from datetime import datetime
from functools import wraps

# Add scripts to path
scripts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts')
sys.path.insert(0, scripts_dir)

from flask import Flask, render_template, jsonify, request, session, send_from_directory
from flask_cors import CORS
import hot_news

app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app, supports_credentials=True)

# Disable caching
@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Secret key
app.secret_key = "hot-news-secret-2026"

# Data paths
DATA_DIR = os.path.expanduser("~/.openclaw/workspace/hot-news")
USERS_FILE = os.path.join(DATA_DIR, "users.json")

os.makedirs(DATA_DIR, exist_ok=True)

# ============== 用户系统 ==============

def load_users():
    """加载用户数据"""
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_users(users):
    """保存用户数据"""
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def get_user_config(user_id):
    """获取用户配置"""
    users = load_users()
    if user_id in users:
        return users[user_id].get('config', {
            'keywords': [],
            'blocked_keywords': [],
            'platforms': ['weibo', 'baidu', 'douyin'],
            'push_enabled': False,
            'push_channel': 'feishu',
            'push_webhook': ''
        })
    return {
        'keywords': [],
        'blocked_keywords': [],
        'platforms': ['weibo', 'baidu', 'douyin'],
        'push_enabled': False,
        'push_channel': 'feishu',
        'push_webhook': ''
    }

def save_user_config(user_id, config):
    """保存用户配置"""
    users = load_users()
    if user_id in users:
        users[user_id]['config'] = config
        save_users(users)

def login_required(f):
    """登录装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({"success": False, "error": "请先登录", "need_login": True})
        return f(*args, **kwargs)
    return decorated

# ============== 路由 ==============

@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json')

@app.route('/sw.js')
def sw():
    return send_from_directory('static', 'sw.js')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/news')
def get_news():
    """获取热点新闻"""
    # 获取配置（优先用户配置，否则默认）
    user_id = session.get('user_id')
    config = get_user_config(user_id) if user_id else {
        'platforms': ['weibo', 'baidu', 'douyin'],
        'keywords': [],
        'blocked_keywords': []
    }
    
    platforms = config.get('platforms', [])
    keywords = config.get('keywords', [])
    blocked = config.get('blocked_keywords', [])
    
    # 获取热点
    all_news = hot_news.fetch_all(platforms if platforms else None)
    
    # 关键词过滤
    if keywords or blocked:
        all_news = hot_news.filter_by_keywords(all_news, keywords, blocked)
    
    return jsonify({
        "success": True,
        "news": all_news[:50],
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "platforms": config.get('platforms', [])
    })

@app.route('/api/config', methods=['GET', 'POST'])
@login_required
def manage_config():
    """获取/保存配置"""
    user_id = session.get('user_id')
    
    if request.method == 'GET':
        return jsonify({"success": True, "config": get_user_config(user_id)})
    
    # POST - 更新配置
    data = request.json or {}
    config = get_user_config(user_id)
    
    # 更新配置项
    for key in ['keywords', 'blocked_keywords', 'platforms', 'push_enabled', 'push_channel', 'push_webhook']:
        if key in data:
            config[key] = data[key]
    
    save_user_config(user_id, config)
    
    return jsonify({"success": True, "message": "配置已保存"})

@app.route('/api/register', methods=['POST'])
def register():
    """注册用户"""
    data = request.json or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({"success": False, "error": "用户名和密码不能为空"})
    
    users = load_users()
    
    # 检查用户名是否已存在
    for user in users.values():
        if user.get('username') == username:
            return jsonify({"success": False, "error": "用户名已存在"})
    
    # 创建新用户
    user_id = hashlib.sha256(username.encode()).hexdigest()[:16]
    users[user_id] = {
        'username': username,
        'password': hashlib.sha256(password.encode()).hexdigest(),
        'config': {
            'keywords': [],
            'blocked_keywords': [],
            'platforms': ['weibo', 'baidu', 'douyin'],
            'push_enabled': False,
            'push_channel': 'feishu',
            'push_webhook': ''
        },
        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    save_users(users)
    
    session['user_id'] = user_id
    session['username'] = username
    
    return jsonify({"success": True, "username": username})

@app.route('/api/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.json or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    users = load_users()
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    user_id = None
    for uid, user in users.items():
        if user.get('username') == username and user.get('password') == password_hash:
            user_id = uid
            break
    
    if not user_id:
        return jsonify({"success": False, "error": "用户名或密码错误"})
    
    session['user_id'] = user_id
    session['username'] = username
    
    return jsonify({"success": True, "username": username})

@app.route('/api/logout', methods=['POST'])
def logout():
    """退出登录"""
    session.clear()
    return jsonify({"success": True})

@app.route('/api/check-login', methods=['GET'])
def check_login():
    """检查登录状态"""
    user_id = session.get('user_id')
    if user_id:
        return jsonify({"success": True, "logged_in": True, "username": session.get('username', '')})
    return jsonify({"success": True, "logged_in": False})

@app.route('/api/push', methods=['POST'])
@login_required
def push_news():
    """推送热点到配置渠道"""
    config = get_user_config(session.get('user_id'))
    
    if not config.get('push_enabled'):
        return jsonify({"success": False, "error": "推送未启用"})
    
    news = hot_news.fetch_all_hot(config.get('platforms', []))
    news = hot_news.filter_by_keywords(news, config.get('keywords'), config.get('blocked_keywords'))
    news = news[:10]
    
    # 生成内容
    content = f"📰 热点资讯 ({datetime.now().strftime('%H:%M')})\n\n"
    for i, item in enumerate(news, 1):
        content += f"{i}. {item['title']}\n"
    
    # 推送
    webhook = config.get('push_webhook', '')
    if config.get('push_channel') == 'feishu' and webhook:
        hot_news.push_to_feishu(webhook, content)
    
    return jsonify({"success": True, "message": "推送成功"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=16888, debug=True)
