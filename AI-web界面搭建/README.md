# 在服务器上执行，直接创建 README.md
cat > /root/README.md << 'EOF'
# WJR MongoDB API 测试平台 - 安装部署指南

## 📋 项目概述

WJR MongoDB API 测试平台是一个基于 KSCC (Kyun Service Cloud Console) 的 API 集成测试工具，主要用于 MongoDB 产品线的接口测试。

### 核心功能

- **📄 固定接口文档**：展示从接口文档解析的 MongoDB API 列表（公共接口/副本集/分片集群）
- **🔍 KSCC AI 扫描接口**：通过 KSCC 的 AI 能力自动扫描发现 MongoDB 产品线的 API
- **🚀 API 请求测试**：可视化构造请求，支持 GET/POST/PUT/DELETE 方法
- **📊 批量测试运行**：一键运行所有 API 测试用例，生成测试报告
- **💬 KSCC AI 对话**：集成 KSCC 的 AI 对话能力（可选）

---

## 🏗️ 目录结构
/root/
├── app.py # 主程序 (HTTP 服务)
├── app.py.backup # 备份文件 (自动生成)
├── kscc_session_id.txt # KSCC 会话ID (运行时生成)
│
├── wjr_test/ # WJR-Test 模块
│ ├── init.py # 模块初始化
│ └── handler.py # 核心处理器
│
├── static/ # 静态文件
│ └── wjr_test/
│ └── index.html # Web 界面
│
└── tmp/
└── app.log # 服务运行日志


## 📦 环境要求

| 组件 | 版本要求 | 说明 |
|------|---------|------|
| 操作系统 | CentOS 7 / RHEL 7 | 或其他 Linux 发行版 |
| Python | 2.7.x | 项目基于 Python 2.7 |
| Docker | 任意版本 | 用于运行 KSCC 容器 |
| 网络 | {宿主机} ↔ {调用端} | 需要互通 |

## 部署
# 创建 WJR-Test 模块目录
mkdir -p /root/wjr_test

# 创建静态文件目录
mkdir -p /root/static/wjr_test

# 创建日志目录（如需要）
mkdir -p /tmp

# 检查文件是否存在
ls -la /root/app.py
ls -la /root/wjr_test/__init__.py
ls -la /root/wjr_test/handler.py
ls -la /root/static/wjr_test/index.html

# 停止旧服务（如果存在）
pkill -f "python /root/app.py"

# 启动服务
nohup python /root/app.py >> /tmp/app.log 2>&1 &

# 查看启动日志
tail -f /tmp/app.log


🌐 访问地址
功能	URL
MongoDB API 测试平台	http://{地址}:8888/wjr-test
KSCC AI 对话	http://{地址}:8888/