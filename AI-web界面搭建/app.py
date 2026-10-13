# -*- coding: utf-8 -*-
import SimpleHTTPServer
import SocketServer
import subprocess
import json
import socket
import threading
import os
import uuid
import hashlib
import time
import sys
import traceback

# ============ WJR-Test 集成 ============
sys.path.insert(0, '/root')
from wjr_test.handler import WJRTestHandler
wjr_handler = WJRTestHandler()
# ======================================

PORT = 8888
TIMEOUT = 600

# ============ 会话存储（多会话） ============
SESSIONS_FILE = '/root/kscc_sessions.json'

CACHE_SIZE = 50

# 响应缓存
response_cache = {}
cache_timestamp = {}


# ============ 会话管理 ============
def load_sessions():
    """读取会话文件，返回 {'current': sid, 'sessions': [ {id,title,started,created_at,updated_at}, ... ]}

    Python 2 下必须用二进制模式读 + 手动 utf-8 decode，否则遇到中文
    会触发 ascii 解码错误。
    """
    if not os.path.exists(SESSIONS_FILE):
        return {'current': None, 'sessions': []}
    try:
        with open(SESSIONS_FILE, 'rb') as f:
            raw = f.read()
        if isinstance(raw, str):
            raw = raw.decode('utf-8')
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError('bad sessions file')
        data.setdefault('current', None)
        data.setdefault('sessions', [])
        return data
    except Exception:
        return {'current': None, 'sessions': []}


def save_sessions(data):
    """保存会话文件。

    Python 2 下 json.dump 直接写文本模式文件会按 ascii 编码 unicode，
    遇到中文（如默认标题"新会话"）会抛 UnicodeEncodeError。
    改为：先 dumps 成 unicode，再显式 encode utf-8，用二进制模式写。
    """
    tmp = SESSIONS_FILE + '.tmp'
    s = json.dumps(data, ensure_ascii=False, indent=2)
    if isinstance(s, unicode):
        s = s.encode('utf-8')
    with open(tmp, 'wb') as f:
        f.write(s)
    os.rename(tmp, SESSIONS_FILE)


def get_current_session_id():
    data = load_sessions()
    cur = data.get('current')
    if not cur:
        return None
    for s in data.get('sessions', []):
        if s.get('id') == cur:
            return cur
    return None


def get_session_title(sid):
    if not sid:
        return u''
    try:
        for s in load_sessions().get('sessions', []):
            if s.get('id') == sid:
                return s.get('title', u'')
    except Exception:
        pass
    return u''


def is_session_started(sid):
    """判断会话是否已经在 kscc 里创建过（发过至少一条消息成功）。

    未创建过的空会话（点"+ 新建"刚生成 UUID），第一次提问必须用
    `kscc --session-id` 创建；只有创建过之后的提问才用 `--resume`。
    """
    if not sid:
        return False
    try:
        for s in load_sessions().get('sessions', []):
            if s.get('id') == sid:
                return bool(s.get('started'))
    except Exception:
        pass
    return False


def mark_session_started(sid):
    """把会话标记为已在 kscc 创建过"""
    if not sid:
        return
    try:
        data = load_sessions()
        for s in data.get('sessions', []):
            if s.get('id') == sid:
                s['started'] = True
                s['updated_at'] = time.time()
                break
        data['current'] = sid
        save_sessions(data)
    except Exception:
        try:
            sys.stderr.write('[mark_session_started error]\n' + traceback.format_exc() + '\n')
            sys.stderr.flush()
        except Exception:
            pass


def create_new_session(session_id=None, title=u'新会话'):
    """新建一个会话并设为当前，返回 session_id"""
    data = load_sessions()
    sid = session_id or str(uuid.uuid4())
    now = time.time()
    data['sessions'].insert(0, {
        'id': sid,
        'title': title,
        'created_at': now,
        'updated_at': now,
        'started': False
    })
    data['current'] = sid
    save_sessions(data)
    return sid


def touch_session(sid, first_msg=None):
    """更新会话 updated_at；若标题仍为默认值，用首条提问前 20 字当标题。
    整个函数用 try/except 包住 —— 它只是副作用，绝不该让 /chat 挂掉。
    """
    if not sid:
        return
    try:
        data = load_sessions()
        for s in data.get('sessions', []):
            if s.get('id') == sid:
                s['updated_at'] = time.time()
                if first_msg and s.get('title') in (u'新会话', u'', None):
                    t = first_msg
                    if isinstance(t, unicode):
                        pass
                    elif isinstance(t, str):
                        t = t.decode('utf-8', 'ignore')
                    else:
                        t = unicode(t)
                    t = t.strip().replace(u'\n', u' ').replace(u'\r', u' ')
                    s['title'] = t[:20] + (u'…' if len(t) > 20 else u'')
                break
        data['current'] = sid
        save_sessions(data)
    except Exception:
        try:
            sys.stderr.write('[touch_session error]\n' + traceback.format_exc() + '\n')
            sys.stderr.flush()
        except Exception:
            pass


def switch_session(sid):
    data = load_sessions()
    for s in data.get('sessions', []):
        if s.get('id') == sid:
            data['current'] = sid
            save_sessions(data)
            return True
    return False


def delete_session(sid):
    data = load_sessions()
    data['sessions'] = [s for s in data.get('sessions', []) if s.get('id') != sid]
    if data.get('current') == sid:
        data['current'] = data['sessions'][0]['id'] if data['sessions'] else None
    save_sessions(data)
    return True


# ============ 缓存 ============
def get_cache_key(msg):
    """生成缓存key"""
    if isinstance(msg, unicode):
        msg = msg.encode('utf-8')
    return hashlib.md5(msg).hexdigest()


def is_cacheable(msg):
    """
    判断这个问题是否允许走缓存。
    """
    if not msg:
        return False
    if isinstance(msg, unicode):
        msg = msg.encode('utf-8')
    msg = msg.strip()

    if msg.startswith('/'):
        return False

    dangerous_keywords = (
        '提交', '推送', 'commit', 'push', 'pull', 'merge',
        '状态', 'status', 'diff', 'log', 'git',
        '执行', 'run', 'exec', 'sql', 'mongo', 'redis',
        '删除', 'drop', 'delete', 'remove', 'reset', 'clear',
        '创建', 'create', '插入', 'insert', 'update', '修改',
        '部署', 'deploy', '重启', 'restart', 'kill',
        '查询', 'select', 'find', 'show',
    )
    low = msg.lower()
    for k in dangerous_keywords:
        if k in low:
            return False

    if len(msg) < 4:
        return False

    return True


def get_cached_response(msg):
    key = get_cache_key(msg)
    if key in response_cache:
        if time.time() - cache_timestamp.get(key, 0) < 3600:
            return response_cache[key]
        else:
            if key in response_cache:
                del response_cache[key]
            if key in cache_timestamp:
                del cache_timestamp[key]
    return None


def set_cached_response(msg, reply):
    key = get_cache_key(msg)
    if len(response_cache) >= CACHE_SIZE:
        if cache_timestamp:
            oldest_key = min(cache_timestamp, key=cache_timestamp.get)
            if oldest_key in response_cache:
                del response_cache[oldest_key]
            if oldest_key in cache_timestamp:
                del cache_timestamp[oldest_key]

    response_cache[key] = reply
    cache_timestamp[key] = time.time()


HTML = r'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Wangjingru 的 Kscc</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            color: #e2e8f0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            overflow: hidden;
        }
        body::before {
            content: '';
            position: fixed;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle at 30% 50%, rgba(124, 58, 237, 0.1) 0%, transparent 60%),
                        radial-gradient(circle at 70% 80%, rgba(139, 92, 246, 0.08) 0%, transparent 60%);
            animation: bgPulse 15s ease-in-out infinite;
            z-index: 0;
        }
        @keyframes bgPulse {
            0%, 100% { transform: scale(1) rotate(0deg); }
            50% { transform: scale(1.1) rotate(3deg); }
        }

        .app-layout {
            display: flex;
            width: 1180px;
            max-width: 98%;
            height: 90vh;
            gap: 16px;
            position: relative;
            z-index: 1;
        }

        .sidebar {
            width: 260px;
            flex-shrink: 0;
            background: rgba(17, 24, 39, 0.92);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-radius: 24px;
            border: 1px solid rgba(124, 58, 237, 0.2);
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.8);
            padding: 18px 14px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .sidebar-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 12px;
            border-bottom: 1px solid rgba(124, 58, 237, 0.15);
            margin-bottom: 12px;
        }
        .sidebar-header .title {
            font-size: 13px;
            font-weight: 700;
            color: #a78bfa;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .sidebar-header .new-btn {
            background: linear-gradient(135deg, #7c3aed, #6d28d9);
            border: none;
            color: #fff;
            border-radius: 8px;
            padding: 5px 10px;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            white-space: nowrap;
        }
        .sidebar-header .new-btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(124, 58, 237, 0.4);
        }
        .session-list {
            flex: 1;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 6px;
            padding-right: 2px;
        }
        .session-list::-webkit-scrollbar { width: 4px; }
        .session-list::-webkit-scrollbar-thumb { background: rgba(124, 58, 237, 0.5); border-radius: 4px; }
        .session-item {
            padding: 9px 10px;
            border-radius: 10px;
            background: rgba(30, 41, 59, 0.55);
            border: 1px solid transparent;
            cursor: pointer;
            font-size: 12px;
            color: #cbd5e1;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 6px;
            transition: all 0.2s;
        }
        .session-item:hover {
            border-color: rgba(124, 58, 237, 0.4);
            background: rgba(124, 58, 237, 0.12);
        }
        .session-item.active {
            background: linear-gradient(135deg, rgba(124, 58, 237, 0.35), rgba(109, 40, 217, 0.35));
            border-color: #7c3aed;
            color: #fff;
            box-shadow: 0 0 0 1px rgba(124, 58, 237, 0.3) inset;
        }
        .session-item .title {
            flex: 1;
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .session-item .meta {
            font-size: 10px;
            color: #64748b;
            margin-top: 2px;
        }
        .session-item .del {
            opacity: 0;
            color: #ef4444;
            font-size: 13px;
            padding: 0 2px;
            flex-shrink: 0;
            transition: opacity 0.2s;
        }
        .session-item:hover .del { opacity: 1; }
        .session-empty {
            text-align: center;
            color: #4b5563;
            font-size: 11px;
            padding: 20px 0;
        }

        .container { 
            flex: 1;
            min-width: 0;
            height: 100%;
            background: rgba(17, 24, 39, 0.92);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-radius: 24px;
            padding: 24px;
            border: 1px solid rgba(124, 58, 237, 0.2);
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.8),
                        0 0 0 1px rgba(124, 58, 237, 0.05) inset;
            display: flex;
            flex-direction: column;
            position: relative;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 16px;
            border-bottom: 1px solid rgba(124, 58, 237, 0.15);
        }
        .header-left {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .header-icon {
            font-size: 28px;
            animation: iconFloat 3s ease-in-out infinite;
        }
        @keyframes iconFloat {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-3px); }
        }
        .header h1 { 
            color: #a78bfa;
            font-size: 22px;
            font-weight: 700;
            background: linear-gradient(135deg, #a78bfa, #8b5cf6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .header-right {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .session-info { 
            font-size: 12px; 
            color: #9ca3af;
            background: rgba(31, 41, 55, 0.8);
            padding: 4px 14px;
            border-radius: 20px;
            border: 1px solid rgba(124, 58, 237, 0.15);
            font-family: 'Courier New', monospace;
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .status-indicator {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
            color: #9ca3af;
        }
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
            transition: all 0.3s ease;
        }
        .status-dot.ready { background: #22c55e; box-shadow: 0 0 8px rgba(34, 197, 94, 0.4); }
        .status-dot.loading { background: #f59e0b; box-shadow: 0 0 8px rgba(245, 158, 11, 0.4); animation: pulse 1s infinite; }
        .status-dot.error { background: #ef4444; box-shadow: 0 0 8px rgba(239, 68, 68, 0.4); }
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(0.9); }
        }
        #chat { 
            flex: 1; 
            overflow-y: auto; 
            background: rgba(15, 23, 42, 0.6);
            border-radius: 12px;
            padding: 20px;
            margin: 16px 0;
            border: 1px solid rgba(30, 41, 59, 0.5);
            scroll-behavior: smooth;
        }
        #chat::-webkit-scrollbar { width: 5px; }
        #chat::-webkit-scrollbar-track { background: transparent; }
        #chat::-webkit-scrollbar-thumb { 
            background: linear-gradient(to bottom, #7c3aed, #6d28d9);
            border-radius: 10px; 
        }
        .msg { 
            padding: 12px 16px; 
            border-radius: 12px; 
            margin: 6px 0;
            max-width: 92%;
            animation: msgSlideIn 0.3s ease-out;
            position: relative;
        }
        @keyframes msgSlideIn {
            from { opacity: 0; transform: translateY(10px) scale(0.98); }
            to { opacity: 1; transform: translateY(0) scale(1); }
        }
        .msg.user { 
            background: linear-gradient(135deg, #7c3aed, #6d28d9);
            margin-left: auto;
            border-bottom-right-radius: 4px;
            box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3);
            white-space: pre-wrap;
            word-break: break-word;
        }
        .msg.ai { 
            background: rgba(30, 41, 59, 0.8);
            border: 1px solid rgba(124, 58, 237, 0.1);
            margin-right: auto;
            border-bottom-left-radius: 4px;
            position: relative;
        }
        .msg.ai::before {
            content: '🤖';
            position: absolute;
            top: -10px;
            left: 10px;
            font-size: 14px;
            background: #1e293b;
            padding: 0 6px;
        }
        .copy-btn {
            position: absolute;
            top: 8px;
            right: 8px;
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid rgba(124, 58, 237, 0.2);
            color: #9ca3af;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            cursor: pointer;
            opacity: 0;
            transition: all 0.3s ease;
            font-family: inherit;
        }
        .msg.ai:hover .copy-btn {
            opacity: 1;
        }
        .copy-btn:hover {
            background: rgba(124, 58, 237, 0.2);
            color: #e2e8f0;
            border-color: #7c3aed;
        }
        .copy-btn.copied {
            background: rgba(34, 197, 94, 0.2);
            color: #22c55e;
            border-color: #22c55e;
        }
        .msg.ai h1, .msg.ai h2, .msg.ai h3 { 
            color: #a78bfa; 
            margin: 8px 0 4px 0; 
        }
        .msg.ai h1 { font-size: 20px; }
        .msg.ai h2 { font-size: 17px; }
        .msg.ai h3 { font-size: 15px; }
        .msg.ai ul, .msg.ai ol { margin: 4px 0 4px 20px; padding: 0; }
        .msg.ai li { margin: 2px 0; }
        .msg.ai code { 
            background: rgba(15, 23, 42, 0.8);
            padding: 2px 8px; 
            border-radius: 4px; 
            font-size: 13px; 
            color: #fbbf24;
            font-family: 'Courier New', monospace;
        }
        .msg.ai pre { 
            background: rgba(15, 23, 42, 0.8);
            padding: 12px 16px; 
            border-radius: 8px; 
            overflow-x: auto; 
            border: 1px solid rgba(30, 41, 59, 0.5);
            font-size: 13px; 
            margin: 8px 0;
            position: relative;
        }
        .msg.ai pre code { 
            background: none; 
            padding: 0; 
            color: #e2e8f0;
        }
        .msg.ai table { 
            border-collapse: collapse; 
            width: 100%; 
            margin: 8px 0; 
            font-size: 13px; 
        }
        .msg.ai th, .msg.ai td { 
            border: 1px solid #374151; 
            padding: 6px 12px; 
            text-align: left; 
        }
        .msg.ai th { 
            background: rgba(31, 41, 55, 0.6);
            color: #a78bfa; 
        }
        .msg.ai blockquote { 
            border-left: 3px solid #7c3aed; 
            margin: 4px 0; 
            padding-left: 12px; 
            color: #9ca3af; 
        }
        .msg.ai hr { border-color: rgba(31, 41, 55, 0.5); margin: 8px 0; }
        .input-area { 
            display: flex; 
            gap: 12px;
            padding-top: 4px;
        }
        .input-area input { 
            flex: 1; 
            padding: 14px 18px; 
            border-radius: 12px; 
            border: 1px solid rgba(55, 65, 81, 0.6);
            background: rgba(15, 23, 42, 0.8);
            color: #fff; 
            font-size: 14px; 
            outline: none;
            transition: all 0.3s ease;
        }
        .input-area input:focus { 
            border-color: #7c3aed;
            box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.2);
        }
        .input-area input::placeholder {
            color: #6b7280;
        }
        .input-area button { 
            padding: 14px 28px; 
            background: linear-gradient(135deg, #7c3aed, #6d28d9);
            border: none; 
            border-radius: 12px; 
            color: #fff; 
            font-weight: 600;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.3s ease;
            white-space: nowrap;
        }
        .input-area button:hover { 
            transform: translateY(-2px);
            box-shadow: 0 4px 20px rgba(124, 58, 237, 0.4);
        }
        .input-area button:active {
            transform: translateY(0px);
        }
        .input-area .clear-btn { 
            background: rgba(239, 68, 68, 0.8);
        }
        .input-area .clear-btn:hover { 
            background: #ef4444;
            box-shadow: 0 4px 20px rgba(239, 68, 68, 0.3);
        }
        .input-area .clear-btn:active {
            transform: translateY(0px);
        }
        .footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid rgba(31, 41, 55, 0.3);
        }
        .footer-info {
            display: flex;
            align-items: center;
            gap: 16px;
            font-size: 12px;
            color: #6b7280;
        }
        .footer-info .badge {
            background: rgba(124, 58, 237, 0.15);
            padding: 2px 10px;
            border-radius: 12px;
            color: #a78bfa;
            font-size: 11px;
        }
        .markdown-body { 
            line-height: 1.7;
            padding-right: 40px;
        }
        .loading-dots {
            display: inline-block;
        }
        .loading-dots::after {
            content: "...";
            animation: dots 1.5s steps(4) infinite;
        }
        @keyframes dots {
            0% { content: ""; }
            25% { content: "."; }
            50% { content: ".."; }
            75% { content: "..."; }
        }
        .toast {
            position: fixed;
            bottom: 30px;
            left: 50%;
            transform: translateX(-50%) translateY(100px);
            background: rgba(17, 24, 39, 0.95);
            backdrop-filter: blur(10px);
            padding: 12px 24px;
            border-radius: 12px;
            border: 1px solid rgba(124, 58, 237, 0.2);
            color: #e2e8f0;
            font-size: 14px;
            opacity: 0;
            transition: all 0.5s ease;
            z-index: 1000;
            pointer-events: none;
        }
        .toast.show {
            opacity: 1;
            transform: translateX(-50%) translateY(0);
        }
        @media (max-width: 900px) {
            .app-layout { flex-direction: column; height: auto; max-height: 95vh; }
            .sidebar { width: 100%; max-height: 30vh; }
            .container { height: 65vh; padding: 16px; }
        }
        @media (max-width: 768px) {
            .header h1 { font-size: 18px; }
            .input-area { flex-wrap: wrap; }
            .input-area input { min-width: 100%; }
            .input-area button { flex: 1; padding: 12px; }
            .msg { max-width: 100%; }
            .session-info { max-width: 120px; }
        }
    </style>
</head>
<body>
<div class="app-layout">
    <aside class="sidebar">
        <div class="sidebar-header">
            <span class="title">💬 历史会话</span>
            <button class="new-btn" onclick="newSession()">+ 新建</button>
        </div>
        <div class="session-list" id="sessionList">
            <div class="session-empty">暂无会话</div>
        </div>
    </aside>

    <div class="container">
        <div class="header">
            <div class="header-left">
                <span class="header-icon">🧠</span>
                <h1>Wangjingru 的 Kscc</h1>
            </div>
            <div class="header-right">
                <span class="session-info" id="sessionInfo">会话: 未开始</span>
                <div class="status-indicator">
                    <span class="status-dot ready" id="statusDot"></span>
                    <span id="statusText">就绪</span>
                </div>
            </div>
        </div>
        
        <div id="chat">
            <div class="msg ai markdown-body">👋 你好！支持**多轮对话**和**响应缓存**。<br>⏱ 响应约 5-6 秒<br>💡 左侧可切换历史会话<br>🔒 命令类 / 状态查询 / 写操作不走缓存，始终实时</div>
        </div>
        
        <div class="input-area">
            <input id="msg" placeholder="输入问题..." onkeydown="if(event.key==='Enter') send()">
            <button onclick="send()">发送</button>
            <button onclick="clearSession()" class="clear-btn">重置</button>
        </div>
        
        <div class="footer">
            <div class="footer-info">
                <span>⚡ 缓存: <span id="cacheStatus">0</span></span>
                <span class="badge">v2.2</span>
            </div>
            <div class="footer-info">
                <span>⏱ <span id="responseTime">-</span></span>
            </div>
        </div>
    </div>
</div>

<div class="toast" id="toast"></div>

<script>
var messageCount = 0;
var startTime = null;
var currentSessionId = null;

function showToast(message, duration) {
    if (duration === undefined) duration = 2000;
    var toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(toast._hideTimeout);
    toast._hideTimeout = setTimeout(function() {
        toast.classList.remove('show');
    }, duration);
}

function copyMessage(text, btn) {
    var tempDiv = document.createElement('div');
    tempDiv.innerHTML = text;
    var plainText = tempDiv.textContent || tempDiv.innerText;
    
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(plainText).then(function() {
            btn.textContent = '✅ 已复制';
            btn.classList.add('copied');
            showToast('✅ 已复制到剪贴板');
            setTimeout(function() {
                btn.textContent = '📋 复制';
                btn.classList.remove('copied');
            }, 2000);
        }).catch(function() {
            fallbackCopy(plainText, btn);
        });
    } else {
        fallbackCopy(plainText, btn);
    }
}

function fallbackCopy(text, btn) {
    var textarea = document.createElement('textarea');
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
    btn.textContent = '✅ 已复制';
    btn.classList.add('copied');
    showToast('✅ 已复制到剪贴板');
    setTimeout(function() {
        btn.textContent = '📋 复制';
        btn.classList.remove('copied');
    }, 2000);
}

function addMsg(text, cls) {
    var chat = document.getElementById('chat');
    var d = document.createElement('div');
    d.className = 'msg ' + cls;
    
    if (cls === 'ai') {
        var content = document.createElement('div');
        content.className = 'markdown-body';
        content.innerHTML = marked.parse(text);
        
        var copyBtn = document.createElement('button');
        copyBtn.className = 'copy-btn';
        copyBtn.textContent = '📋 复制';
        copyBtn.onclick = function(e) {
            e.stopPropagation();
            copyMessage(text, this);
        };
        
        d.appendChild(content);
        d.appendChild(copyBtn);
    } else {
        d.textContent = text;
    }
    
    chat.appendChild(d);
    chat.scrollTop = chat.scrollHeight;
    return d;
}

function addMsgWithTyping(text, cls) {
    var chat = document.getElementById('chat');
    var d = document.createElement('div');
    d.className = 'msg ' + cls;
    
    if (cls === 'ai') {
        var content = document.createElement('div');
        content.className = 'markdown-body';
        d.appendChild(content);
        
        var copyBtn = document.createElement('button');
        copyBtn.className = 'copy-btn';
        copyBtn.style.opacity = '0';
        copyBtn.onclick = function(e) {
            e.stopPropagation();
            copyMessage(fullText, this);
        };
        d.appendChild(copyBtn);
        
        chat.appendChild(d);
        chat.scrollTop = chat.scrollHeight;
        
        var fullText = text;
        var i = 0;
        var speed = 2;
        var chunkSize = 3;
        
        function typeWriter() {
            if (i < fullText.length) {
                var chunk = fullText.substring(i, Math.min(i + chunkSize, fullText.length));
                i = Math.min(i + chunkSize, fullText.length);
                content.innerHTML = marked.parse(fullText.substring(0, i));
                chat.scrollTop = chat.scrollHeight;
                var delay = speed;
                if (chunk.match(/[。，！？；：、\\n]/)) {
                    delay = speed * 3;
                }
                setTimeout(typeWriter, delay);
            } else {
                copyBtn.style.opacity = '1';
            }
        }
        typeWriter();
    } else {
        d.textContent = text;
        chat.appendChild(d);
        chat.scrollTop = chat.scrollHeight;
    }
    return d;
}

function addLoading() {
    var chat = document.getElementById('chat');
    var d = document.createElement('div');
    d.className = 'msg ai markdown-body';
    d.id = 'loading';
    d.innerHTML = '⏳ <span class="loading-dots">思考中</span>';
    chat.appendChild(d);
    chat.scrollTop = chat.scrollHeight;
}

function removeLoading() {
    var el = document.getElementById('loading');
    if (el) el.remove();
}

function updateSessionInfo(sessionId, title) {
    var el = document.getElementById('sessionInfo');
    if (!sessionId) {
        el.textContent = '会话: 未开始';
        el.title = '';
        return;
    }
    if (title) {
        el.textContent = title;
        el.title = title + ' (' + sessionId + ')';
    } else {
        el.textContent = '会话: ' + sessionId.substring(0, 8) + '...';
        el.title = sessionId;
    }
}

function updateStatus(status, text) {
    var dot = document.getElementById('statusDot');
    var statusText = document.getElementById('statusText');
    dot.className = 'status-dot';
    if (status === 'ready') {
        dot.classList.add('ready');
        statusText.textContent = text || '就绪';
    } else if (status === 'loading') {
        dot.classList.add('loading');
        statusText.textContent = text || '处理中...';
    } else if (status === 'error') {
        dot.classList.add('error');
        statusText.textContent = text || '错误';
    }
}

function updateCacheStatus(count) {
    document.getElementById('cacheStatus').textContent = count;
}

function updateResponseTime(time) {
    document.getElementById('responseTime').textContent = time + 's';
}

function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function(c) {
        return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
}

function formatTime(ts) {
    if (!ts) return '';
    var d = new Date(ts * 1000);
    var now = new Date();
    var pad = function(n) { return n < 10 ? '0' + n : '' + n; };
    if (d.toDateString() === now.toDateString()) {
        return pad(d.getHours()) + ':' + pad(d.getMinutes());
    }
    return (d.getMonth() + 1) + '/' + d.getDate();
}

function loadSessions() {
    fetch('/sessions')
    .then(function(r) { return r.json(); })
    .then(function(d) {
        var list = document.getElementById('sessionList');
        var sessions = d.sessions || [];
        var cur = d.current;
        currentSessionId = cur;
        if (!sessions.length) {
            list.innerHTML = '<div class="session-empty">暂无会话</div>';
            updateSessionInfo(null);
            return;
        }
        var html = '';
        for (var i = 0; i < sessions.length; i++) {
            var s = sessions[i];
            var cls = 'session-item' + (s.id === cur ? ' active' : '');
            html += '<div class="' + cls + '" data-sid="' + escapeHtml(s.id) + '">'
                  +   '<div style="flex:1;min-width:0">'
                  +     '<div class="title" title="' + escapeHtml(s.title || '新会话') + '">'
                  +       escapeHtml(s.title || '新会话')
                  +     '</div>'
                  +     '<div class="meta">' + formatTime(s.updated_at || s.created_at) + '</div>'
                  +   '</div>'
                  +   '<span class="del" title="删除">✕</span>'
                  + '</div>';
        }
        list.innerHTML = html;

        var items = list.querySelectorAll('.session-item');
        for (var k = 0; k < items.length; k++) {
            (function(el) {
                var sid = el.getAttribute('data-sid');
                el.addEventListener('click', function(e) {
                    if (e.target.classList.contains('del')) {
                        e.stopPropagation();
                        if (confirm('删除这个会话？')) deleteSession(sid);
                        return;
                    }
                    switchSession(sid);
                });
            })(items[k]);
        }

        if (cur) {
            var curTitle = '';
            for (var m = 0; m < sessions.length; m++) {
                if (sessions[m].id === cur) { curTitle = sessions[m].title || ''; break; }
            }
            updateSessionInfo(cur, curTitle);
        } else {
            updateSessionInfo(null);
        }
    })
    ['catch'](function() {
        document.getElementById('sessionList').innerHTML = '<div class="session-empty">加载失败</div>';
    });
}

function newSession() {
    fetch('/sessions/new', { method: 'POST' })
    .then(function(r) { return r.json(); })
    .then(function(d) {
        if (d.status === 'ok') {
            currentSessionId = d.session_id;
            document.getElementById('chat').innerHTML =
                '<div class="msg ai markdown-body">🆕 新会话已创建，开始提问吧！</div>';
            updateSessionInfo(d.session_id, '新会话');
            updateStatus('ready', '新会话');
            loadSessions();
            document.getElementById('msg').focus();
        }
    });
}

function switchSession(sid) {
    if (sid === currentSessionId) return;
    fetch('/sessions/switch', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({session_id: sid})
    })
    .then(function(r) { return r.json(); })
    .then(function(d) {
        if (d.status === 'ok') {
            currentSessionId = sid;
            document.getElementById('chat').innerHTML =
                '<div class="msg ai markdown-body">🔄 已切换会话 <code>' +
                escapeHtml(sid.substring(0,8)) + '...</code><br>继续提问将接续该会话上下文。</div>';
            updateSessionInfo(sid);
            updateStatus('ready', '已切换');
            loadSessions();
            document.getElementById('msg').focus();
        }
    });
}

function deleteSession(sid) {
    fetch('/sessions/delete', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({session_id: sid})
    })
    .then(function(r) { return r.json(); })
    .then(function() {
        if (sid === currentSessionId) {
            document.getElementById('chat').innerHTML =
                '<div class="msg ai markdown-body">🗑 当前会话已删除</div>';
            updateSessionInfo(null);
        }
        loadSessions();
    });
}

function clearSession() {
    if (confirm('重置会清空所有会话历史，确定吗？')) {
        fetch('/clear', { method: 'POST' })
        .then(function(r) { return r.json(); })
        .then(function(d) {
            if (d.status === 'ok') {
                document.getElementById('chat').innerHTML = '<div class="msg ai markdown-body">✅ 所有会话已清空！</div>';
                updateSessionInfo(null);
                updateStatus('ready', '已重置');
                loadSessions();
            }
        });
    }
}

function send() {
    var msg = document.getElementById('msg');
    if (!msg.value.trim()) return;
    
    var userMsg = msg.value.trim();
    addMsg(userMsg, 'user');
    msg.value = '';
    updateStatus('loading', '处理中...');
    addLoading();
    
    startTime = Date.now();

    var controller = new AbortController();
    var timeoutId = setTimeout(function() { controller.abort(); }, 600000);

    fetch('/chat', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({message: userMsg}),
        signal: controller.signal
    })
    .then(function(r) { clearTimeout(timeoutId); return r.text(); })
    .then(function(txt) {
        var d;
        try { d = JSON.parse(txt); }
        catch (e) {
            removeLoading();
            updateStatus('error', '解析失败');
            addMsg('❌ 服务端返回不是合法 JSON：\n\n' + (txt ? txt.substring(0, 500) : '(空)'), 'ai');
            return;
        }
        removeLoading();
        updateStatus('ready', '已回复');
        
        if (d.session_id) {
            currentSessionId = d.session_id;
            updateSessionInfo(d.session_id, d.session_title);
        }
        
        if (d.from_cache) {
            updateCacheStatus(d.cache_count || '?');
            updateStatus('ready', '⚡ 来自缓存');
            setTimeout(function() { updateStatus('ready', '已回复'); }, 1500);
        } else {
            updateCacheStatus(d.cache_count || '?');
        }
        
        if (startTime) {
            var elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
            updateResponseTime(elapsed);
        }
        
        addMsgWithTyping(d.reply || '无响应', 'ai');
        loadSessions();
    })
    .catch(function(e) {
        removeLoading();
        clearTimeout(timeoutId);
        updateStatus('error', '错误');
        if (e.name === 'AbortError') {
            addMsg('⏰ 请求超时（10分钟）', 'ai');
        } else {
            addMsg('请求失败: ' + e.message, 'ai');
        }
    });
}

window.addEventListener('DOMContentLoaded', function() {
    loadSessions();
});
</script>
</body>
</html>
'''


class Handler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    timeout = 300

    def log_error(self, format, *args):
        if 'Broken pipe' in format % args:
            return
        SimpleHTTPServer.SimpleHTTPRequestHandler.log_error(self, format, *args)

    def handle_error(self, request, client_address):
        try:
            sys.stderr.write('[Handler uncaught]\n' + traceback.format_exc() + '\n')
            sys.stderr.flush()
        except Exception:
            pass

    def handle_one_request(self):
        try:
            SimpleHTTPServer.SimpleHTTPRequestHandler.handle_one_request(self)
        except socket.error as e:
            if e.errno != 32:
                raise
        except Exception as e:
            if 'Broken pipe' not in str(e):
                raise

    def _read_json_body(self):
        try:
            length = int(self.headers.getheader('Content-Length', 0))
            body = self.rfile.read(length)
            return json.loads(body) if body else {}
        except Exception:
            return {}

    def _send_json(self, obj, status=200):
        try:
            self.send_response(status)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            body = json.dumps(obj, ensure_ascii=False)
            if isinstance(body, unicode):
                body = body.encode('utf-8')
            self.wfile.write(body)
        except Exception:
            try:
                sys.stderr.write('[send_json error]\n' + traceback.format_exc() + '\n')
                sys.stderr.flush()
            except Exception:
                pass

    def do_GET(self):
        # ============ WJR-Test 路由 ============
        if self.path == '/wjr-test' or self.path == '/wjr-test/':
            try:
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                with open('/root/static/wjr_test/index.html', 'r') as f:
                    self.wfile.write(f.read())
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write('Error loading page: ' + str(e))
            return

        if self.path == '/wjr-test/api/discover':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            result = wjr_handler.handle_discover()
            self.wfile.write(json.dumps(result))
            return

        if self.path == '/wjr-test/api/fixed-apis':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            result = wjr_handler.handle_fixed_apis()
            self.wfile.write(json.dumps(result))
            return

        if self.path == '/wjr-test/bg.jpg':
            try:
                self.send_response(200)
                self.send_header('Content-type', 'image/jpeg')
                self.end_headers()
                with open('/home/wangjingru/IMG_4929.jpg', 'rb') as f:
                    self.wfile.write(f.read())
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write('Error loading image: ' + str(e))
            return

        if self.path == '/wjr-test/api/products':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            result = wjr_handler.handle_products()
            self.wfile.write(json.dumps(result))
            return

        if self.path.startswith('/wjr-test/api/sql-meta'):
            # 解析 ?target=nova|k8s (不带默认nova)
            target = 'nova'
            parts = self.path.split('?', 1)
            if len(parts) == 2:
                for kv in parts[1].split('&'):
                    if kv.startswith('target=') and kv[7:] in ('nova', 'k8s'):
                        target = kv[7:]
            try:
                self.send_response(200)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                result = wjr_handler.handle_sql_meta(target)
                self.wfile.write(json.dumps(result, ensure_ascii=False))
            except Exception as e:
                try:
                    self.wfile.write(json.dumps({
                        'success': False,
                        'tables': [],
                        'columns': {},
                        'error': str(e)
                    }, ensure_ascii=False))
                except Exception:
                    pass
            return

        # ============ 会话列表接口 ============
        if self.path == '/sessions':
            self._send_json(load_sessions())
            return

        if self.path.startswith('/wjr-test'):
            self.send_response(404)
            self.end_headers()
            self.wfile.write('Not Found')
            return

        # ============ 原有逻辑 ============
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(HTML)

    def do_POST(self):
        # ============ WJR-Test API 路由 ============
        if self.path.startswith('/wjr-test/api/'):
            data = self._read_json_body()

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            if self.path == '/wjr-test/api/test':
                result = wjr_handler.handle_test(data)
            elif self.path == '/wjr-test/api/flow-trace':
                result = wjr_handler.handle_flow_trace(data)
            elif self.path == '/wjr-test/api/list-flows':
                result = wjr_handler.handle_list_flows(data)
            elif self.path == '/wjr-test/api/flow-detail':
                result = wjr_handler.handle_flow_detail(data)
            elif self.path == '/wjr-test/api/list-resources':
                result = wjr_handler.handle_list_resources(data)
            elif self.path == '/wjr-test/api/run-tests':
                result = wjr_handler.handle_run_tests(data)
            elif self.path == '/wjr-test/api/flow-retry':
                result = wjr_handler.handle_flow_retry(data)
            elif self.path == '/wjr-test/api/execute-sql':
                result = wjr_handler.handle_execute_sql(data)
            else:
                result = {'success': False, 'error': '未知API: ' + self.path}

            try:
                self.wfile.write(json.dumps(result))
            except Exception:
                pass
            return
        # ============ WJR-Test API 路由结束 ============

        # ============ 会话相关接口 ============
        if self.path == '/sessions/new':
            sid = create_new_session()
            self._send_json({'status': 'ok', 'session_id': sid})
            return

        if self.path == '/sessions/switch':
            data = self._read_json_body()
            sid = data.get('session_id')
            if sid and switch_session(sid):
                self._send_json({'status': 'ok', 'session_id': sid})
            else:
                self._send_json({'status': 'error', 'error': 'session not found'}, 404)
            return

        if self.path == '/sessions/delete':
            data = self._read_json_body()
            sid = data.get('session_id')
            if sid:
                delete_session(sid)
            self._send_json({'status': 'ok'})
            return
        # =====================================

        # ============ 原有 /clear 逻辑 ============
        if self.path == '/clear':
            if os.path.exists(SESSIONS_FILE):
                try:
                    os.remove(SESSIONS_FILE)
                except Exception:
                    pass
            response_cache.clear()
            cache_timestamp.clear()
            self._send_json({'status': 'ok'})
            return

        # ============ 原有 /chat 逻辑 ============
        if self.path == '/chat':
            reply = u''
            from_cache = False
            try:
                data = self._read_json_body()
                msg = data.get('message', '')

                if isinstance(msg, unicode):
                    msg = msg.encode('utf-8')

                cached_reply = None
                if is_cacheable(msg):
                    cached_reply = get_cached_response(msg)

                if cached_reply:
                    from_cache = True
                    reply = cached_reply
                    sid_now = get_current_session_id()
                    if sid_now:
                        touch_session(sid_now, first_msg=msg)
                else:
                    try:
                        safe_msg = msg.replace("'", "'\\''")
                        session_id = get_current_session_id()

                        pending_sid = None
                        if session_id and is_session_started(session_id):
                            sid_b = session_id
                            if isinstance(sid_b, unicode):
                                sid_b = sid_b.encode('utf-8')
                            cmd = "docker exec wjrKscc sh -c \"kscc --resume %s -p '%s' < /dev/null\"" % (sid_b, safe_msg)
                            touch_session(session_id, first_msg=msg)
                            pending_sid = session_id
                        else:
                            if session_id:
                                new_session = session_id
                            else:
                                new_session = create_new_session()
                            sid_b = new_session
                            if isinstance(sid_b, unicode):
                                sid_b = sid_b.encode('utf-8')
                            cmd = "docker exec wjrKscc sh -c \"kscc --session-id %s -p '%s' < /dev/null\"" % (sid_b, safe_msg)
                            touch_session(new_session, first_msg=msg)
                            pending_sid = new_session

                        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, close_fds=True)

                        timed_out = [False]

                        def _kill_on_timeout():
                            timed_out[0] = True
                            try:
                                proc.kill()
                            except Exception:
                                pass

                        timer = threading.Timer(TIMEOUT, _kill_on_timeout)
                        timer.start()

                        try:
                            out, err = proc.communicate()
                            timer.cancel()
                            if timed_out[0]:
                                reply = u"⏰ 请求超时（%d秒）" % TIMEOUT
                            elif proc.returncode == 0:
                                reply = out.decode('utf-8', 'replace').strip()
                                if not reply:
                                    reply = u"（kscc 没有返回内容）"
                                if pending_sid:
                                    mark_session_started(pending_sid)
                                if is_cacheable(msg) and not reply.startswith(u'错误') and not reply.startswith(u'异常') and not reply.startswith(u'⏰'):
                                    set_cached_response(msg, reply)
                            else:
                                reply = u"错误: " + err.decode('utf-8', 'replace').strip()
                        except Exception:
                            timer.cancel()
                            try:
                                proc.kill()
                            except Exception:
                                pass
                            reply = u"⏰ 请求超时（%d秒）" % TIMEOUT
                    except Exception as e:
                        try:
                            sys.stderr.write('[chat inner error]\n' + traceback.format_exc() + '\n')
                            sys.stderr.flush()
                        except Exception:
                            pass
                        reply = u"异常: " + unicode(e)
            except Exception as e:
                reply = u"服务端异常: " + unicode(e)
                try:
                    sys.stderr.write('[chat outer error]\n' + traceback.format_exc() + '\n')
                    sys.stderr.flush()
                except Exception:
                    pass

            sid = get_current_session_id()
            try:
                title = get_session_title(sid)
            except Exception:
                title = u''
            self._send_json({
                'reply': reply,
                'session_id': sid,
                'session_title': title,
                'from_cache': from_cache,
                'cache_count': len(response_cache)
            })
            return

        # 其他POST请求返回404
        self.send_response(404)
        self.end_headers()
        self.wfile.write('Not Found')


if __name__ == '__main__':
    import socket
    SocketServer.TCPServer.allow_reuse_address = True

    print '=========================================='
    print 'Wangjingru 的 Kscc Web 服务已启动！'
    print '访问地址: http://<APP_HOST>:' + str(PORT)
    print '超时时间: ' + str(TIMEOUT) + ' 秒'
    print '缓存大小: ' + str(CACHE_SIZE) + ' 条'
    print '会话文件: ' + SESSIONS_FILE
    print '支持: 多会话侧边栏 | 响应缓存 | 打字机效果 | 消息复制'
    print 'WJR-Test: http://<APP_HOST>:' + str(PORT) + '/wjr-test'
    print '=========================================='
    SocketServer.ThreadingTCPServer(('0.0.0.0', PORT), Handler).serve_forever()