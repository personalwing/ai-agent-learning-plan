# AI Web 界面搭建

一个基于 Python 2.7 的轻量 Web 工具，提供 KSCC AI 对话、MongoDB API 接口测试和只读 SQL 查询代理功能。

## 功能

- KSCC AI 多轮对话，支持响应缓存和会话 ID 保存。
- MongoDB API 测试平台：固定接口列表、接口扫描、单接口请求和批量测试。
- 支持 `GET`、`POST`、`PUT`、`DELETE` 请求及 JSON 请求体、请求头和分页参数。
- SQL 查询代理：仅允许 `SELECT`、`SHOW` 和 `DESCRIBE` 查询。
- Web 服务使用多线程 HTTP 服务，默认监听 `8888` 端口。

## 目录结构

```text
AI-web界面搭建/
├── app.py                    # 主 Web 服务和 KSCC AI 对话接口
├── sql_proxy.py              # 只读 SQL 查询代理，默认监听 5001
├── wjr_test/
│   ├── __init__.py           # WJR-Test 模块
│   └── handler.py            # API 测试、扫描和批量运行逻辑
└── static/
    └── wjr_test/
        └── index.html        # MongoDB API 测试前端
```

运行时可能生成以下文件：

- `kscc_session_id.txt`：KSCC 对话会话 ID。
- `response_cache.json`：响应缓存文件（如果启用持久化缓存）。

## 环境要求

- Linux 或其他支持 Python 2.7 的系统。
- Python 2.7。
- Python 包：`requests`。
- 如果使用 SQL 代理，还需要安装 `mysql` 命令行客户端，并能访问目标 MySQL 实例。
- 网络能够访问 KSCC API 服务。

安装 Python 依赖：

```bash
python2 -m pip install requests
```

## 配置敏感信息

仓库中的真实 IP、Token、项目 ID 和密码已替换为占位符。启动前需要在以下文件中填入实际配置，或按项目后续配置方案改为环境变量：

- `wjr_test/handler.py`
  - `<KSCC_HOST>`
  - `<SQL_PROXY_HOST>`
  - `<PROJECT_ID>`
  - `<AUTH_TOKEN>`
  - `<APPLICATION_TOKEN>`
  - `<ADMIN_PASSWORD>`
  - `<VPC_ID>`
  - `<VNET_ID>`
- `static/wjr_test/index.html`
  - `<KSCC_HOST>`
  - `<PROJECT_ID>`
  - `<AUTH_TOKEN>`
  - `<APPLICATION_TOKEN>`
- `sql_proxy.py`
  - `<DB_PASSWORD>`（也可用环境变量 `TROVE_DB_PASSWORD` 注入，避免真实密码写进代码）

不要将真实凭据提交到 Git。建议使用本地配置文件、环境变量或部署系统的密钥管理功能保存生产配置。

## 启动

### 1. 启动 SQL 代理（可选）

SQL 代理连接本机 `127.0.0.1:3307` 上的 MySQL，监听 `5001` 端口：

```bash
cd AI-web界面搭建
python2 sql_proxy.py
```

健康检查：

```bash
curl http://127.0.0.1:5001/health
```

### 2. 启动 Web 服务

```bash
cd AI-web界面搭建
python2 app.py
```

默认服务地址：

- AI 对话：`http://<APP_HOST>:8888/`
- MongoDB API 测试平台：`http://<APP_HOST>:8888/wjr-test`

其中 `<APP_HOST>` 替换为部署主机地址。服务绑定在 `0.0.0.0:8888`，可根据部署环境配置防火墙和反向代理。

## API 测试使用流程

1. 打开 `/wjr-test`。
2. 在固定接口列表中选择 MongoDB 接口，或点击扫描获取接口。
3. 填写 `{tenant_id}`、资源 ID、请求参数和请求体。
4. 点击发送执行单个请求，或运行批量测试。
5. 使用右侧结果区域查看响应和生成的 `curl` 请求。

分页参数支持 `page` 和 `limit`，程序会自动转换为后端使用的 `offset` 和 `limit`。

## 安全注意事项

- SQL 代理只允许只读查询，但仍应限制监听端口的访问来源。
- 不要把生产 Token、数据库密码或内部 IP 写入前端静态文件。
- 部署到共享网络前，应增加身份认证、HTTPS 和访问控制。
- 提交前可以扫描敏感信息：

```bash
grep -RIn --exclude-dir=.git -Ei \
  'password|passwd|secret|token|api[_-]?key|([0-9]{1,3}\.){3}[0-9]{1,3}' \
  AI-web界面搭建
```
