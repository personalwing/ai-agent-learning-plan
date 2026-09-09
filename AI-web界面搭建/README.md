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

## 🏗️ 系统架构
