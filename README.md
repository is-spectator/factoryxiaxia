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
│   ├── extensions.py           # Flask 扩展实例 (db, limiter)
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
│   │   └── test_api.py         # API 测试 (63 cases)
│   ├── init.sql                # 数据库初始化 + 种子数据
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
./deploy.sh
```

启动后：

- 前端：http://localhost:10088
- 后端 API：http://localhost:5000
- 数据库：localhost:3306

默认管理员账号：`admin` / `admin123456`

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

当前测试覆盖 63 个用例，包括：
- 用户认证（注册/登录/禁用用户拦截）
- 订单全流程（创建/支付/激活/完成/退款/取消）
- 状态机校验（管理员非法状态变更拦截）
- 消息触发（所有核心动作均验证消息生成）
- 收藏、评价、推荐
- 安全头、限流、API 文档

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

1. 创建 `.env` 文件并修改所有默认密码和密钥
2. 确认 `.env` 已加入 `.gitignore`
3. 修改 `JWT_SECRET` 为随机强密钥（至少 32 位）
4. 修改 `DB_PASS` 和 `MYSQL_ROOT_PASSWORD`
5. 配置 HTTPS（在 Nginx 或负载均衡层）

## 环境差异

| 环境 | 数据库 | 密钥 | 限流 |
|------|--------|------|------|
| 开发 | MySQL (docker) | 默认值 | 宽松 |
| 测试 | SQLite 内存 | test-secret | 关闭 |
| 生产 | MySQL (独立) | 必须自定义 (.env) | 严格 |

生产部署前必须修改 `.env` 中的密码和密钥，参考 `.env.example`。
