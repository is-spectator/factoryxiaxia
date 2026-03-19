# 虾虾工厂 | XiaXia Factory

2026 领先的数字员工租赁平台 —— 公司官网

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | HTML + Tailwind CSS + Iconify |
| 后端 | Python Flask + Gunicorn |
| 数据库 | MySQL 8.0 |
| 认证 | bcrypt 密码哈希 + JWT Token |
| 部署 | Docker Compose |

## 项目结构

```
├── docker-compose.yml          # 容器编排 (nginx + flask + mysql)
├── deploy.sh                   # 一键部署脚本
├── backend/
│   ├── Dockerfile
│   ├── app.py                  # Flask 应用入口（初始化 + 蓝图注册）
│   ├── manage.py               # 数据库迁移命令入口
│   ├── extensions.py           # Flask 扩展实例 (db, limiter)
│   ├── migration_manager.py    # 迁移状态表 + 迁移执行器
│   ├── migrations/             # 版本化迁移脚本
│   ├── models.py               # SQLAlchemy 数据模型
│   ├── routes/
│   │   ├── auth.py             # 注册、登录、个人信息
│   │   ├── catalog.py          # 分类、员工、评价、推荐
│   │   ├── orders.py           # 订单、支付、消息、收藏
│   │   ├── admin.py            # 管理后台接口
│   │   └── system.py           # 健康检查、API 文档
│   ├── services/
│   │   └── messages.py         # 站内消息服务
│   ├── utils/
│   │   ├── auth.py             # JWT 认证工具
│   │   └── helpers.py          # 通用工具函数
│   ├── tests/
│   │   ├── conftest.py         # 测试配置 (SQLite monkey-patch)
│   │   └── test_api.py         # API 测试 (80+ cases)
│   ├── init.sql                # 当前结构快照（用于对照，不再作为生产建库入口）
│   ├── requirements.txt        # 运行依赖
│   └── requirements-test.txt   # 测试依赖
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf              # Nginx 反向代理配置
│   ├── index.html              # 首页
│   ├── login.html / register.html
│   ├── workers.html / worker-detail.html
│   ├── order-create.html / pay.html / orders.html / order-detail.html
│   ├── profile.html / messages.html
│   └── admin*.html             # 管理后台页面
└── web_ui_design_v2/           # UI 设计稿
```

## 快速部署

前置要求：已安装 Docker 和 Docker Compose。

```bash
# 本地开发
./deploy.sh

# 生产部署
cp .env.example .env
# 编辑 .env，至少设置：
# APP_ENV=production
# MYSQL_ROOT_PASSWORD / DB_PASS / JWT_SECRET
# PUBLIC_BASE_URL / ALLOWED_ORIGINS
# ADMIN_INIT_PASSWORD
# PUBLIC_CHAT_IP_LIMIT_PER_MINUTE / PUBLIC_CHAT_DEPLOYMENT_LIMIT_PER_MINUTE
./deploy.sh prod
```

`deploy.sh` 现在会先启动数据库，再显式执行：

```bash
docker compose run --rm backend python manage.py migrate
```

迁移成功后才会启动后端和前端服务。

启动后：

- 开发环境前端：http://localhost:10088
- 开发环境后端 API：http://localhost:5000
- 生产环境 API：通过前端网关访问 `/api/*`

生产环境不再内置默认管理员账号。
如果数据库里还没有 `admin` 用户，首次启动会读取 `ADMIN_INIT_*` 环境变量创建一次性管理员。
生产环境默认走“付款确认 -> 后台确认收款”模式，不再提供一键支付成功的假支付链路。
生产环境如果存在未执行迁移，后端会直接拒绝启动并提示先运行 `python manage.py migrate`。

## API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/register` | 用户注册 |
| POST | `/api/login` | 用户登录 |
| GET | `/api/profile` | 获取用户信息（需 Bearer Token） |
| GET | `/api/categories` | 获取分类列表 |
| GET | `/api/workers` | 获取员工列表 |
| GET | `/api/orders` | 获取我的订单（需 Token） |
| GET | `/api/health` | 健康检查 |

### 注册

```bash
curl -X POST http://localhost:10088/api/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@example.com","password":"12345678","confirm_password":"12345678"}'
```

### 登录

```bash
curl -X POST http://localhost:10088/api/login \
  -H "Content-Type: application/json" \
  -d '{"login_id":"test","password":"12345678"}'
```

### 查看个人信息

```bash
curl http://localhost:10088/api/profile \
  -H "Authorization: Bearer <token>"
```

## 本地测试

无需 MySQL，测试自动使用 SQLite 内存数据库：

```bash
cd backend
pip install -r requirements-test.txt
python -m pytest tests/ -v
```

当前测试覆盖 70+ 个用例，包括：
- 用户认证（注册/登录/禁用用户拦截）
- 订单全流程（创建/支付/激活/完成/退款/取消）
- 状态机校验（管理员非法状态变更拦截）
- 消息触发（所有核心动作均验证消息生成）
- 收藏、评价、推荐
- 安全头、限流、API 文档

## 数据库迁移

数据库结构变更现在通过版本化迁移管理，不再依赖应用启动时自动补列。

```bash
cd backend
python manage.py status
python manage.py migrate
```

上线顺序建议固定为：

```bash
# 1. 先备份
# 2. 再迁移
docker compose run --rm backend python manage.py migrate

# 3. 最后启动应用
docker compose up -d backend frontend
```

## Docker 部署后冒烟检查

```bash
# 启动服务
docker compose up -d

# 等待服务就绪后执行冒烟检查
curl -s http://localhost:10088/api/health | python3 -m json.tool
# 预期: {"status": "ok", "database": "connected", ...}

curl -s http://localhost:10088/api/categories | python3 -m json.tool
# 预期: {"categories": [...]}

curl -s -X POST http://localhost:10088/api/register \
  -H "Content-Type: application/json" \
  -d '{"username":"smoketest","email":"smoke@test.com","password":"Test1234","confirm_password":"Test1234"}'
# 预期: 201 + token
```

## 常用命令

```bash
# 查看日志
docker compose logs -f

# 只看后端日志
docker compose logs backend --tail=50

# 停止服务
docker compose down

# 重新构建并启动
docker compose up --build -d

# 清除数据重新开始
docker compose down -v
```

## 故障排查

### 注册/登录返回 500 (INTERNAL SERVER ERROR)

1. **检查后端日志**：

```bash
docker compose logs backend --tail=50
```

2. **常见原因**：

| 现象 | 原因 | 解决方案 |
|------|------|----------|
| `ModuleNotFoundError` | 后端镜像未包含所有源码 | `docker compose up --build -d` 重新构建 |
| `Can't connect to MySQL` | MySQL 尚未就绪或已崩溃 | `docker compose restart db`，等 10 秒后 `docker compose restart backend` |
| `Table 'xxx' doesn't exist` | 数据库初始化未完成 | `docker compose down -v && docker compose up -d` 清除数据重建 |
| `Duplicate entry` | 用户名或邮箱已存在 | 换一个用户名/邮箱，或 `docker compose down -v` 清库重来 |

3. **确认 MySQL 可达**：

```bash
docker compose exec backend python -c "
from app import app, db
with app.app_context():
    db.engine.connect()
    print('数据库连接正常')
"
```

### 服务无法访问 (Connection refused)

```bash
# 确认所有容器都在运行
docker compose ps

# 如果某个容器 Exited，查看原因
docker compose logs <服务名>

# 重新构建并启动
docker compose up --build -d
```

### MySQL 容器反复重启

```bash
# 查看 MySQL 日志
docker compose logs db --tail=30

# 可能是数据卷损坏，清除后重建
docker compose down -v
docker compose up -d
```

### 前端页面无法调用后端 API (502 Bad Gateway)

前端通过 Nginx 反向代理访问后端（`/api/*` → `backend:5000`），请确认：

```bash
# 1. 所有容器正在运行
docker compose ps

# 2. 后端健康检查通过
curl http://localhost:10088/api/health

# 3. 如果返回 502，说明 Nginx 无法连接后端容器
docker compose restart backend
```

### 生产环境安全检查

部署到公网前，务必完成以下步骤：

1. 创建 `.env` 文件并设置 `APP_ENV=production`
2. 确认 `.env` 已加入 `.gitignore`
3. 设置强随机 `JWT_SECRET`（至少 32 位）
4. 设置 `DB_PASS` 和 `MYSQL_ROOT_PASSWORD`
5. 设置 `PUBLIC_BASE_URL` 和 `ALLOWED_ORIGINS`
6. 设置一次性 `ADMIN_INIT_PASSWORD` 完成管理员初始化
7. 设置 `PUBLIC_CHAT_IP_LIMIT_PER_MINUTE` 和 `PUBLIC_CHAT_DEPLOYMENT_LIMIT_PER_MINUTE`
8. 配置 HTTPS（在 Nginx 或负载均衡层）
9. 确认生产环境支付链路使用“付款确认 / 后台确认收款”，不要对外暴露开发环境快捷支付

### 公开 API 访问规则

- 管理后台域名白名单由 `.env` 中的 `ALLOWED_ORIGINS` 控制
- 公开聊天接口 `/api/public/chat/<public_token>/message` 支持服务端直接调用
- 如果你要把机器人挂件嵌入浏览器页面，必须在部署向导里为每个机器人单独配置 `allowed_origins`
- 浏览器来源不在部署白名单内时，公开 API 会拒绝访问并写入审计日志

## 环境差异

| 环境 | 数据库 | 密钥 | 限流 |
|------|--------|------|------|
| 开发 | MySQL (docker) | 本地配置 | 宽松 |
| 测试 | SQLite 内存 | test-secret | 关闭 |
| 生产 | MySQL (docker / 独立) | 必须自定义 (.env) | 严格 |

生产部署前必须修改 `.env` 中的密码和密钥，并通过 `docker-compose.prod.yml` 收起数据库和后端的公网端口。
