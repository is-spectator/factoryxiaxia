# 虾虾工厂 部署运维手册

## 1. 环境要求

| 组件 | 最低版本 |
|------|---------|
| Docker | 24.0+ |
| Docker Compose | 2.20+ |
| 内存 | 2GB+ |
| 磁盘 | 10GB+ |

## 2. 快速部署

```bash
# 1) 克隆代码
git clone <repo-url> && cd factoryxiaxia

# 2) 创建环境配置
cp .env.example .env
# 编辑 .env
# 生产环境至少需要：
# APP_ENV=production
# MYSQL_ROOT_PASSWORD / DB_PASS / JWT_SECRET
# PUBLIC_BASE_URL / ALLOWED_ORIGINS
# ADMIN_INIT_PASSWORD
# PUBLIC_CHAT_IP_LIMIT_PER_MINUTE / PUBLIC_CHAT_DEPLOYMENT_LIMIT_PER_MINUTE

# 3) 开发环境启动
./deploy.sh

# 4) 生产环境启动
./deploy.sh prod

# 5) 验证
curl http://localhost:10088/api/health
```

服务启动后：
- 开发环境前端访问：`http://<host>:10088`
- 开发环境后端 API：`http://<host>:5000/api/`
- 生产环境 API：`http://<host>/api/`
- API 文档：`http://<host>/api/docs`
- 生产环境支付：默认走“付款确认 -> 后台确认收款”
- 数据库迁移：启动前会先执行 `python manage.py migrate`

## 3. 环境变量说明

| 变量 | 说明 | 默认值 |
|------|------|-------|
| `DB_USER` | MySQL 用户名 | xiaxia |
| `MYSQL_ROOT_PASSWORD` | MySQL root 密码 | 必填 |
| `DB_PASS` | MySQL 密码 | 必填 |
| `DB_HOST` | MySQL 地址 | db |
| `DB_NAME` | 数据库名 | xiaxia_factory |
| `APP_ENV` | 应用环境 | development / production |
| `JWT_SECRET` | JWT 签名密钥 | 必填 |
| `PUBLIC_BASE_URL` | 对外访问根地址 | 必填（生产） |
| `ALLOWED_ORIGINS` | 允许访问 API 的前端域名列表 | 必填（生产） |
| `PUBLIC_CHAT_IP_LIMIT_PER_MINUTE` | 公开聊天接口按 IP 限流阈值 | 30 |
| `PUBLIC_CHAT_DEPLOYMENT_LIMIT_PER_MINUTE` | 公开聊天接口按部署实例限流阈值 | 120 |
| `ADMIN_INIT_USERNAME` | 首次管理员用户名 | admin |
| `ADMIN_INIT_EMAIL` | 首次管理员邮箱 | admin@xiaxia.factory |
| `ADMIN_INIT_PASSWORD` | 首次管理员密码 | 必填（生产首次启动） |
| `FLASK_ENV` | Flask 环境 | development（生产请改为 production） |
| `RATE_LIMIT_DEFAULT` | 默认限流 | 60/minute |
| `RATE_LIMIT_AUTH` | 认证接口限流 | 10/minute |
| `ALERT_WEBHOOK_URL` | 告警 Webhook 地址 | (空) |

## 4. 管理员初始化

- 生产环境不再内置默认管理员账号
- 如果数据库中还没有 `admin` 角色用户，首次启动时会读取 `ADMIN_INIT_*` 环境变量自动创建一次性管理员
- 首次登录后请立刻修改管理员密码，并从运行环境中移除 `ADMIN_INIT_PASSWORD`

## 5. 常用运维命令

```bash
# 查看日志
docker compose logs -f backend
docker compose logs -f db

# 重启后端
docker compose restart backend

# 重建并更新
docker compose up -d --build

# 查看迁移状态
docker compose run --rm backend python manage.py status

# 执行迁移
docker compose run --rm backend python manage.py migrate

# 生产模式
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 进入数据库
docker exec -it xiaxia-db mysql -u xiaxia -p xiaxia_factory

# 清理数据（危险操作）
docker compose down -v  # 删除所有数据卷
```

## 5.1 公开 API 白名单与限流

- `.env` 里的 `ALLOWED_ORIGINS` 只控制管理后台和平台前端自己的跨域访问
- 对外售卖机器人的浏览器来源白名单，按部署实例存储在部署配置 `allowed_origins`
- 客户如果通过浏览器挂件调用公开接口，必须在部署向导里填入其站点域名
- 服务端直接调用 `POST /api/public/chat/<public_token>/message` 时，不需要浏览器 Origin 白名单
- 公开 API 访问会记录来源域名、来源 IP、UA，并对非法 Origin、异常 Referer、限流和额度耗尽写审计日志
- 生产环境不再提供开发环境快捷支付按钮；客户提交付款确认后，需要运营后台执行“确认收款”

## 6. 备份与恢复

```bash
# 备份数据库
docker exec xiaxia-db mysqldump -u xiaxia -p"$DB_PASS" xiaxia_factory > backup_$(date +%Y%m%d).sql

# 恢复数据库
docker exec -i xiaxia-db mysql -u xiaxia -p"$DB_PASS" xiaxia_factory < backup_20260316.sql
```

### 6.1 迁移与回滚流程

上线前请固定按下面顺序执行：

```bash
# 1. 备份数据库
docker exec xiaxia-db mysqldump -u xiaxia -p"$DB_PASS" xiaxia_factory > backup_before_migrate.sql

# 2. 查看待执行迁移
docker compose run --rm backend python manage.py status

# 3. 执行迁移
docker compose run --rm backend python manage.py migrate

# 4. 再启动应用
docker compose up -d backend frontend
```

如果迁移失败：

```bash
# 1. 停止应用，避免半升级状态继续提供服务
docker compose stop backend frontend

# 2. 回滚数据库
docker exec -i xiaxia-db mysql -u xiaxia -p"$DB_PASS" xiaxia_factory < backup_before_migrate.sql

# 3. 修复迁移问题后重新执行 migrate
docker compose run --rm backend python manage.py migrate
```

## 7. 监控与告警

- 健康检查端点：`GET /api/health`
  - 返回 `200` 表示正常，`503` 表示数据库异常
- 配置 `ALERT_WEBHOOK_URL` 环境变量可接入钉钉/飞书/Slack 告警
- 后端日志为 JSON 格式（structured logging），可对接 ELK/Loki 等日志平台

## 8. 安全建议

1. **修改默认密码**：部署后立即修改 `.env` 中所有密码和 JWT_SECRET
2. **管理员初始化**：首次启动依赖 `ADMIN_INIT_PASSWORD`，初始化完成后应立即移除
3. **HTTPS**：生产环境建议在 Nginx 前加一层反向代理启用 HTTPS
4. **防火墙**：仅暴露 80/443 端口，MySQL 3306 和后端 5000 不要对外
5. **定期备份**：建议每日自动备份数据库
6. **日志监控**：接入日志平台，关注 5xx 错误和异常登录
7. **先迁移再启动**：生产环境不要跳过 `python manage.py migrate`
