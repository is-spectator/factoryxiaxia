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
# 编辑 .env，修改密码和 JWT_SECRET

# 3) 启动服务
docker compose up -d --build

# 4) 验证
curl http://localhost:10088          # 前端页面
curl http://localhost:5000/api/health # 后端健康检查
```

服务启动后：
- 前端访问：`http://<host>:10088`
- 后端 API：`http://<host>:5000/api/`
- API 文档：`http://<host>:5000/api/docs`

## 3. 环境变量说明

| 变量 | 说明 | 默认值 |
|------|------|-------|
| `DB_USER` | MySQL 用户名 | xiaxia |
| `DB_PASS` | MySQL 密码 | xiaxia_secret_2026 |
| `DB_HOST` | MySQL 地址 | db |
| `DB_NAME` | 数据库名 | xiaxia_factory |
| `JWT_SECRET` | JWT 签名密钥 | xiaxia-jwt-secret-key-2026 |
| `FLASK_ENV` | Flask 环境 | production |
| `RATE_LIMIT_DEFAULT` | 默认限流 | 60/minute |
| `RATE_LIMIT_AUTH` | 认证接口限流 | 10/minute |
| `ALERT_WEBHOOK_URL` | 告警 Webhook 地址 | (空) |

## 4. 默认账户

| 角色 | 用户名 | 密码 |
|------|--------|-----|
| 管理员 | admin | admin123456 |

**部署后请立即修改管理员密码。**

## 5. 常用运维命令

```bash
# 查看日志
docker compose logs -f backend
docker compose logs -f db

# 重启后端
docker compose restart backend

# 重建并更新
docker compose up -d --build

# 进入数据库
docker exec -it xiaxia-db mysql -u xiaxia -p xiaxia_factory

# 清理数据（危险操作）
docker compose down -v  # 删除所有数据卷
```

## 6. 备份与恢复

```bash
# 备份数据库
docker exec xiaxia-db mysqldump -u xiaxia -p'xiaxia_secret_2026' xiaxia_factory > backup_$(date +%Y%m%d).sql

# 恢复数据库
docker exec -i xiaxia-db mysql -u xiaxia -p'xiaxia_secret_2026' xiaxia_factory < backup_20260316.sql
```

## 7. 监控与告警

- 健康检查端点：`GET /api/health`
  - 返回 `200` 表示正常，`503` 表示数据库异常
- 配置 `ALERT_WEBHOOK_URL` 环境变量可接入钉钉/飞书/Slack 告警
- 后端日志为 JSON 格式（structured logging），可对接 ELK/Loki 等日志平台

## 8. 安全建议

1. **修改默认密码**：部署后立即修改 `.env` 中所有密码和 JWT_SECRET
2. **HTTPS**：生产环境建议在 Nginx 前加一层反向代理启用 HTTPS
3. **防火墙**：仅暴露 80/443 端口，MySQL 3306 端口不要对外
4. **定期备份**：建议每日自动备份数据库
5. **日志监控**：接入日志平台，关注 5xx 错误和异常登录
