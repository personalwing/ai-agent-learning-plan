# -*- coding: utf-8 -*-
import SimpleHTTPServer
import SocketServer
import subprocess
import json
import signal
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
SESSION_FILE = '/root/kscc_session_id.txt'
CACHE_SIZE = 50

# 响应缓存
response_cache = {}
cache_timestamp = {}

def get_cache_key(msg):
    """生成缓存key"""
    return hashlib.md5(msg.encode('utf-8')).hexdigest()

def get_cached_response(msg):
    """获取缓存响应"""
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
    """设置缓存响应"""
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

HTML = '''
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
        .container { 
            width: 920px; 
            max-width: 96%; 
            height: 90vh; 
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
            z-index: 1;
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
        @media (max-width: 768px) {
            .container { padding: 16px; height: 95vh; }
            .header h1 { font-size: 18px; }
            .input-area { flex-wrap: wrap; }
            .input-area input { min-width: 100%; }
            .input-area button { flex: 1; padding: 12px; }
            .msg { max-width: 100%; }
        }
    </style>
</head>
<body>
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
        <div class="msg ai markdown-body">👋 你好！支持**多轮对话**和**响应缓存**。<br>⏱ 响应约 5-6 秒<br>💡 悬停消息可复制内容</div>
    </div>
    
    <div class="input-area">
        <input id="msg" placeholder="输入问题..." onkeydown="if(event.key==='Enter') send()">
        <button onclick="send()">发送</button>
        <button onclick="clearSession()" class="clear-btn">重置</button>
    </div>
    
    <div class="footer">
        <div class="footer-info">
            <span>⚡ 缓存: <span id="cacheStatus">0</span></span>
            <span class="badge">v2.0</span>
        </div>
        <div class="footer-info">
            <span>⏱ <span id="responseTime">-</span></span>
        </div>
    </div>
</div>

<div class="toast" id="toast"></div>

<script>
var messageCount = 0;
var startTime = null;

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
        })['catch'](function() {
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
                var btn = d.querySelector('.copy-btn');
                if (btn) btn.style.opacity = '1';
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

function updateSessionInfo(sessionId) {
    if (sessionId) {
        document.getElementById('sessionInfo').textContent = '会话: ' + sessionId.substring(0, 8) + '...';
    } else {
        document.getElementById('sessionInfo').textContent = '会话: 未开始';
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

function clearSession() {
    if (confirm('确定要重置会话吗？')) {
        fetch('/clear', { method: 'POST' })
        .then(function(r) { return r.json(); })
        .then(function(d) {
            if (d.status === 'ok') {
                document.getElementById('chat').innerHTML = '<div class="msg ai markdown-body">✅ 会话已重置！</div>';
                updateSessionInfo(null);
                updateStatus('ready', '已重置');
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
    .then(function(r) { clearTimeout(timeoutId); return r.json(); })
    .then(function(d) {
        removeLoading();
        updateStatus('ready', '已回复');
        
        if (d.session_id) {
            updateSessionInfo(d.session_id);
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
    })
    ['catch'](function(e) {
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
</script>
</body>
</html>
'''

def get_session_id():
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, 'r') as f:
            return f.read().strip()
    return None

def save_session_id(session_id):
    with open(SESSION_FILE, 'w') as f:
        f.write(session_id)

class Handler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    # 增加超时处理，防止Broken pipe
    timeout = 300
    
    def log_error(self, format, *args):
        # 忽略 Broken pipe 错误
        if 'Broken pipe' in format % args:
            return
        SimpleHTTPServer.SimpleHTTPRequestHandler.log_error(self, format, *args)
    
    def handle_one_request(self):
        try:
            SimpleHTTPServer.SimpleHTTPRequestHandler.handle_one_request(self)
        except socket.error as e:
            # 忽略 Broken pipe 错误
            if e.errno != 32:  # EPIPE
                raise
        except Exception as e:
            if 'Broken pipe' not in str(e):
                raise
    
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
        
        if self.path == '/wjr-test/api/products':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            result = wjr_handler.handle_products()
            self.wfile.write(json.dumps(result))
            return
        
        if self.path.startswith('/wjr-test'):
            self.send_response(404)
            self.end_headers()
            self.wfile.write('Not Found')
            return
        # ============ WJR-Test 路由结束 ============
        
        # ============ 原有逻辑 ============
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(HTML)

    def do_POST(self):
        # ============ WJR-Test API 路由 ============
        if self.path.startswith('/wjr-test/api/'):
            try:
                length = int(self.headers.getheader('Content-Length', 0))
                body = self.rfile.read(length)
                data = json.loads(body) if body else {}
            except Exception as e:
                data = {}
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            if self.path == '/wjr-test/api/test':
                result = wjr_handler.handle_test(data)
            elif self.path == '/wjr-test/api/run-tests':
                result = wjr_handler.handle_run_tests(data)
            else:
                result = {'success': False, 'error': '未知API: ' + self.path}
            
            try:
                self.wfile.write(json.dumps(result))
            except Exception as e:
                # 忽略 Broken pipe
                pass
            return
        # ============ WJR-Test API 路由结束 ============
        
        # ============ 原有 /clear 逻辑 ============
        if self.path == '/clear':
            if os.path.exists(SESSION_FILE):
                os.remove(SESSION_FILE)
            response_cache.clear()
            cache_timestamp.clear()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok'}))
            return
        
        # ============ 原有 /chat 逻辑 ============
        if self.path == '/chat':
            length = int(self.headers.getheader('Content-Length', 0))
            body = self.rfile.read(length)
            data = json.loads(body)
            msg = data.get('message', '')

            cached_reply = get_cached_response(msg)
            from_cache = False
            
            if cached_reply:
                from_cache = True
                reply = cached_reply
                print '使用缓存响应: %s...' % msg[:30]
            else:
                try:
                    safe_msg = msg.replace("'", "'\\''")
                    session_id = get_session_id()

                    if session_id:
                        cmd = "docker exec wjrKscc sh -c \"kscc --resume %s -p '%s' < /dev/null\"" % (session_id, safe_msg)
                    else:
                        new_session = str(uuid.uuid4())
                        cmd = "docker exec wjrKscc sh -c \"kscc --session-id %s -p '%s' < /dev/null\"" % (new_session, safe_msg)
                        save_session_id(new_session)

                    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, close_fds=True)

                    # 用 threading.Timer 替代 signal.alarm（signal 只能在主线程用，
                    # ThreadingTCPServer 下 /chat 在子线程执行会抛
                    # "signal only works in main thread"）
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
                            reply = "⏰ 请求超时（%d秒）" % TIMEOUT
                        elif proc.returncode == 0:
                            reply = out.decode('utf-8').strip()
                            if not reply:
                                reply = "（kscc 没有返回内容）"
                            set_cached_response(msg, reply)
                        else:
                            reply = "错误: " + err.decode('utf-8').strip()
                    except Exception:
                        timer.cancel()
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        reply = "⏰ 请求超时（%d秒）" % TIMEOUT
                except Exception as e:
                    reply = "异常: " + str(e)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'reply': reply,
                'session_id': get_session_id(),
                'from_cache': from_cache,
                'cache_count': len(response_cache)
            }))
            return
        
        # 其他POST请求返回404
        self.send_response(404)
        self.end_headers()
        self.wfile.write('Not Found')

if __name__ == '__main__':
    # 用 ThreadingTCPServer，避免 /chat 的 docker exec 长耗时阻塞 wjr-test 测试请求
    import socket
    SocketServer.TCPServer.allow_reuse_address = True

    print '=========================================='
    print 'Wangjingru 的 Kscc Web 服务已启动！'
    print '访问地址: http://{服务端地址}:' + str(PORT)
    print '超时时间: ' + str(TIMEOUT) + ' 秒'
    print '缓存大小: ' + str(CACHE_SIZE) + ' 条'
    print '支持: 多轮对话 | 响应缓存 | 打字机效果 | 消息复制'
    print 'WJR-Test: http://{服务端地址}:' + str(PORT) + '/wjr-test'
    print '=========================================='
    SocketServer.ThreadingTCPServer(('0.0.0.0', PORT), Handler).serve_forever()