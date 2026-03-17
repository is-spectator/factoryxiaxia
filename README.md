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
│   ├── init.sql                # 数据库初始化
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

## API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/register` | 用户注册 |
| POST | `/api/login` | 用户登录 |
| GET | `/api/profile` | 获取用户信息（需 Bearer Token） |
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

# 停止服务
docker compose down

# 重新构建并启动
docker compose up --build -d

# 清除数据重新开始
docker compose down -v
```

## 环境差异

| 环境 | 数据库 | 密钥 | 限流 |
|------|--------|------|------|
| 开发 | MySQL (docker) | 默认值 | 宽松 |
| 测试 | SQLite 内存 | test-secret | 关闭 |
| 生产 | MySQL (独立) | 必须自定义 (.env) | 严格 |

生产部署前必须修改 `.env` 中的密码和密钥，参考 `.env.example`。
