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
├── docker-compose.yml        # 容器编排 (nginx + flask + mysql)
├── deploy.sh                 # 一键部署脚本
├── backend/
│   ├── Dockerfile
│   ├── app.py                # Flask API
│   ├── init.sql              # 数据库初始化
│   └── requirements.txt
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf            # Nginx 反向代理配置
│   ├── index.html            # 首页
│   ├── login.html            # 登录
│   ├── register.html         # 注册
│   └── profile.html          # 个人中心
└── web_ui_design_v2/         # UI 设计稿
```

## 快速部署

前置要求：已安装 Docker 和 Docker Compose。

```bash
./deploy.sh
```

启动后：

- 前端：http://localhost
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
curl -X POST http://localhost/api/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@example.com","password":"12345678","confirm_password":"12345678"}'
```

### 登录

```bash
curl -X POST http://localhost/api/login \
  -H "Content-Type: application/json" \
  -d '{"login_id":"test","password":"12345678"}'
```

### 查看个人信息

```bash
curl http://localhost/api/profile \
  -H "Authorization: Bearer <token>"
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
