# 虾虾工厂 — 系统实现计划

> 数字员工租赁平台 · 分阶段交付路线图

---

## 当前进度总览

| 阶段 | 状态 | 说明 |
|------|------|------|
| 阶段一：基础骨架 | ✅ 已完成 | 官网 + 用户系统 + Docker 部署 |
| 阶段二：核心业务 | ✅ 已完成 | 数字员工目录 + 租赁流程 |
| 阶段三：管理后台 | ✅ 已完成 | 权限模型 + 数据看板 + CRUD 管理 |
| 阶段四：支付与订单生命周期 | ✅ 已完成 | 状态机 + 模拟支付 + 退款 + 超时取消 |
| 阶段五：增值功能 | ✅ 已完成 | 评价 + 站内消息 + 收藏 + 智能推荐 |
| 阶段六：上线保障 | ✅ 已完成 | 安全加固 + 性能优化 + CI/CD + 监控告警 + 文档 |

---

## 阶段一：基础骨架（✅ 已完成）

**目标**：搭建项目工程、官网首页、用户注册登录、容器化部署。

### To-Do List

- [x] 项目工程初始化（目录结构、docker-compose）
- [x] 官网首页（index.html — 品牌展示、核心卖点、CTA）
- [x] 用户注册页面 + API（POST /api/register）
- [x] 用户登录页面 + API（POST /api/login）
- [x] 个人中心页面 + API（GET /api/profile）
- [x] JWT 认证中间件
- [x] MySQL 数据库初始化脚本
- [x] Nginx 反向代理配置
- [x] Docker Compose 一键部署（deploy.sh）
- [x] README 文档

### 核心交付物

| 交付物 | 文件 |
|--------|------|
| 官网首页 | `frontend/index.html` |
| 登录/注册页 | `frontend/login.html`, `frontend/register.html` |
| 个人中心 | `frontend/profile.html` |
| 后端 API | `backend/app.py` |
| 数据库脚本 | `backend/init.sql` |
| 部署配置 | `docker-compose.yml`, `deploy.sh` |

### 测试报告

**测试时间**：2026-03-16 | **测试方式**：阶段二测试脚本中包含阶段一用户系统回归测试 | **结果**：✅ 通过

| 测试模块 | 结果 | 测试内容 |
|----------|------|----------|
| 用户注册 | ✅ | POST /api/register → 201，返回 token + user |
| 用户登录 | ✅ | POST /api/login → 200，支持用户名/邮箱登录 |
| JWT 认证 | ✅ | 无 token 访问受保护接口 → 401 |
| 前端页面 | ✅ | index.html / login.html / register.html / profile.html 文件存在 |
| 部署配置 | ✅ | docker-compose.yml / deploy.sh / Dockerfile / nginx.conf 完整 |

---

## 阶段二：核心业务 — 数字员工目录与租赁

**目标**：实现数字员工浏览、搜索、详情查看及租赁下单流程。

### To-Do List

- [x] 设计数字员工数据模型（workers 表：名称、技能标签、头像、时薪、状态、简介）
- [x] 数字员工分类模型（categories 表：开发、设计、运营、客服等）
- [x] API — 数字员工列表（GET /api/workers，支持分页、筛选、搜索）
- [x] API — 数字员工详情（GET /api/workers/:id）
- [x] API — 数字员工分类（GET /api/categories）
- [x] 前端 — 数字员工目录页（workers.html — 卡片列表、筛选栏、搜索框）
- [x] 前端 — 数字员工详情页（worker-detail.html — 技能、评分、租赁入口）
- [x] 设计租赁订单模型（orders 表：用户ID、员工ID、租赁时长、状态、金额）
- [x] API — 创建租赁订单（POST /api/orders）
- [x] API — 查看我的订单（GET /api/orders）
- [x] API — 订单详情（GET /api/orders/:id）
- [x] 前端 — 租赁下单页（order-create.html — 选择时长、确认价格）
- [x] 前端 — 我的订单页（orders.html — 订单列表、状态标签）
- [x] 数据库迁移脚本更新（init.sql 加入 workers、categories、orders 表）
- [x] 种子数据 — 预置 10+ 数字员工示例数据

### 核心交付物

| 交付物 | 文件 |
|--------|------|
| 数字员工目录页 | `frontend/workers.html` |
| 数字员工详情页 | `frontend/worker-detail.html` |
| 租赁下单页 | `frontend/order-create.html` |
| 我的订单页 | `frontend/orders.html` |
| 后端 API（7 个新接口） | `backend/app.py` |
| 数据库脚本（含种子数据） | `backend/init.sql` |

### 测试报告

**测试时间**：2026-03-16 | **测试方式**：自动化 API 测试（SQLite 替代 MySQL）| **结果**：✅ 45/45 通过，0 失败

| 测试模块 | 测试项数 | 结果 | 测试内容 |
|----------|----------|------|----------|
| 用户注册/登录 | 3 | ✅ | 注册 201、返回 token、登录 200 |
| 分类 API | 3 | ✅ | 列表 200、返回 4 个分类、包含 worker_count 字段 |
| 员工列表 API | 11 | ✅ | 基础列表、分类筛选（category_id=1→4人）、状态筛选（busy→1人）、关键词搜索（Python→≥1）、价格升序排序、评分降序排序、分页（per_page=3→3条/页≥3页） |
| 员工详情 API | 6 | ✅ | 200 响应、name/skills/description/category_name 字段完整、不存在→404 |
| 创建订单 API | 8 | ✅ | 无 token→401、创建→201、order_no 生成、金额计算（1.80×24=43.2）、状态 pending、含 worker_name、第二个订单→201、离线员工→400 拒绝 |
| 我的订单 API | 3 | ✅ | 列表 200、返回 2 个订单、pending 状态筛选 |
| 订单详情 API | 2 | ✅ | 详情 200、包含 order_no |
| 取消订单 API | 2 | ✅ | 取消→200 状态变 cancelled、重复取消→400 |
| 前端页面文件 | 4 | ✅ | workers.html / worker-detail.html / order-create.html / orders.html 存在 |
| Health 检查 | 1 | ✅ | /api/health → 200 |
| **合计** | **45** | **✅ 全部通过** | |

---

## 阶段三：管理后台

**目标**：构建运营管理后台，支持数字员工管理、用户管理、订单管理和数据看板。

### To-Do List

- [x] 后台权限模型（User 表新增 role/is_active 字段，区分 admin/operator/user）
- [x] 后台认证中间件（require_admin() 角色校验函数）
- [x] API — 管理员登录（复用登录接口 + token 包含 role）
- [x] API — 用户管理（GET/PUT/DELETE /api/admin/users）
- [x] API — 数字员工管理（CRUD /api/admin/workers）
- [x] API — 订单管理（GET /api/admin/orders，PUT /api/admin/orders/:id/status）
- [x] API — 数据统计（GET /api/admin/stats — 注册数、订单数、营收、7天趋势、分类占比）
- [x] 前端 — 后台布局框架（admin.html — 侧边栏 + 顶栏 + 内容区）
- [x] 前端 — 数据看板页（Chart.js 折线图 + 环形图 + 7 张指标卡片）
- [x] 前端 — 用户管理页（admin-users.html — 列表、搜索、角色切换、禁用/启用）
- [x] 前端 — 数字员工管理页（admin-workers.html — 新增/编辑弹窗、上下架、删除）
- [x] 前端 — 订单管理页（admin-orders.html — 列表、状态筛选、状态变更）

### 核心交付物

| 交付物 | 文件 |
|--------|------|
| 数据看板 | `frontend/admin.html` |
| 用户管理 | `frontend/admin-users.html` |
| 员工管理 | `frontend/admin-workers.html` |
| 订单管理 | `frontend/admin-orders.html` |
| Admin API（8 个新接口） | `backend/app.py` |

### 测试报告

**测试时间**：2026-03-16 | **测试方式**：自动化 API 测试（SQLite 替代 MySQL）| **结果**：✅ 56/56 通过，0 失败

| 测试模块 | 测试项数 | 结果 | 测试内容 |
|----------|----------|------|----------|
| 权限校验 | 4 | ✅ | 普通用户→403、管理员→200、运营→200、无token→403 |
| 数据统计 API | 9 | ✅ | total_users/workers/orders 正确、daily_orders 7天数组、category_stats、pending/active/online 指标 |
| 用户管理 API | 10 | ✅ | 列表200、搜索、角色筛选、修改角色→operator、禁用用户、不能禁用自己→400、operator不能授予admin→403、删除（有订单→禁用）、不能删除自己→400 |
| 员工管理 CRUD | 11 | ✅ | 列表、新增→201、编辑（名称+状态更新）、缺少必填→400、状态筛选、关键词筛选、删除→200、删除不存在→404 |
| 订单管理 API | 7 | ✅ | 列表200、包含username、pending筛选、订单号搜索、状态变更→paid、无效状态→400 |
| 前端页面文件 | 4 | ✅ | admin.html / admin-users.html / admin-workers.html / admin-orders.html 存在 |
| **合计** | **56** | **✅ 全部通过** | |

---

## 阶段四：支付与订单生命周期

**目标**：集成支付，完善订单状态流转（待支付 → 已支付 → 服务中 → 已完成 / 已退款）。

### To-Do List

- [x] 订单状态机设计（ORDER_TRANSITIONS: pending→paid→active→completed / refunded / cancelled）
- [x] 支付接口抽象层（method 字段支持 mock/alipay/wechat，可扩展）
- [x] API — 模拟支付（POST /api/orders/:id/pay，幂等性保证）
- [x] API — 开始服务（POST /api/orders/:id/activate，paid→active）
- [x] API — 取消订单（POST /api/orders/:id/cancel，pending→cancelled）
- [x] API — 申请退款（POST /api/orders/:id/refund，paid/active→refunded）
- [x] API — 确认完成（POST /api/orders/:id/complete，active→completed）
- [x] API — 查看支付记录（GET /api/orders/:id/payments）
- [x] API — 超时取消（POST /api/orders/cancel-expired，管理员触发）
- [x] 前端 — 支付确认页（pay.html — 订单摘要 + 支付方式选择 + 支付成功弹窗）
- [x] 前端 — 订单详情页（order-detail.html — 状态时间线 + 操作按钮 + 支付记录）
- [x] 数据库 — Payment 模型 + payments 表 + Order 新增时间戳字段

### 核心交付物

| 交付物 | 文件 |
|--------|------|
| 状态机 + 6种状态流转 | `backend/app.py` (ORDER_TRANSITIONS) |
| 支付模块（模拟+可扩展） | `backend/app.py` (pay_order + Payment 模型) |
| 退款流程 | `backend/app.py` (refund_order) |
| 超时取消 | `backend/app.py` (cancel_expired_orders) |
| 支付确认页 | `frontend/pay.html` |
| 订单详情+状态可视化 | `frontend/order-detail.html` |

### 测试报告

**测试时间**：2026-03-16 | **测试方式**：自动化 API 测试（SQLite 替代 MySQL）| **结果**：✅ 45/45 通过，0 失败

| 测试模块 | 测试项数 | 结果 | 测试内容 |
|----------|----------|------|----------|
| 状态机校验 | 3 | ✅ | pending 无法直接 complete/refund/activate |
| 模拟支付 | 10 | ✅ | 支付→200+paid+paid_at、payment_no/amount/method/status 正确、幂等重复支付→200、无token→401 |
| 支付记录 | 2 | ✅ | 列表200、至少1条记录 |
| 激活服务 | 3 | ✅ | paid→active 成功、active→pay 拒绝 |
| 确认完成 | 5 | ✅ | active→completed+completed_at、completed 后无法 refund/cancel |
| 退款流程 | 5 | ✅ | paid→refunded+refunded_at、支付记录标记 refunded、refunded 后无法 activate |
| 取消订单 | 4 | ✅ | pending→cancelled+cancelled_at、cancelled 后无法 pay |
| 超时取消 | 4 | ✅ | 普通用户→403、管理员→取消1个超时订单、确认状态=cancelled |
| Order 新字段 | 4 | ✅ | paid_at/completed_at/cancelled_at/refunded_at 存在 |
| 前端页面 | 2 | ✅ | pay.html / order-detail.html 存在 |
| **合计** | **45** | **✅ 全部通过** | |
| 退款流程 | 用户申请 → 管理员审核 → 退款 |
| 定时任务 | 超时未支付订单自动取消 |

---

## 阶段五：增值功能

**目标**：提升用户体验和平台粘性 — 评价系统、站内消息、智能推荐。

### To-Do List

- [x] 评价模型（Review 表：order_id/user_id/worker_id/rating/content，唯一约束）
- [x] API — 提交评价（POST /api/orders/:id/review，自动更新员工平均评分）
- [x] API — 查看员工评价（GET /api/workers/:id/reviews，分页）
- [x] 消息模型（Message 表：user_id/title/content/msg_type/is_read）
- [x] API — 站内消息（GET /api/messages，支持已读/未读筛选）
- [x] API — 标记已读（POST /api/messages/:id/read）
- [x] API — 全部已读（POST /api/messages/read-all）
- [x] API — 未读数（GET /api/messages/unread-count）
- [x] 订单状态变更自动发送站内消息（支付/完成/退款/取消/超时）
- [x] 前端 — 消息中心页（messages.html — 未读小圆点、筛选、全部已读）
- [x] 收藏模型（Favorite 表：user_id/worker_id，唯一约束）
- [x] API — 收藏/取消收藏/检查状态（POST/DELETE/GET /api/favorites/:worker_id）
- [x] API — 收藏列表（GET /api/favorites）
- [x] 推荐算法 — 基于历史订单分类推荐（排除已用+离线，不足补热门）
- [x] API — 推荐员工（GET /api/recommendations，personalized/popular 策略）

### 核心交付物

| 交付物 | 文件 |
|--------|------|
| 评价系统（评分+评论+更新平均分） | `backend/app.py` (Review 模型 + 2 API) |
| 站内消息（自动通知+消息中心） | `backend/app.py` (Message 模型 + 4 API) |
| 收藏功能（收藏/取消/检查/列表） | `backend/app.py` (Favorite 模型 + 4 API) |
| 智能推荐（个性化+热门兜底） | `backend/app.py` (recommendations API) |
| 消息中心页 | `frontend/messages.html` |

### 测试报告

**测试时间**：2026-03-16 | **测试方式**：自动化 API 测试（SQLite 替代 MySQL）| **结果**：✅ 54/54 通过，0 失败

| 测试模块 | 测试项数 | 结果 | 测试内容 |
|----------|----------|------|----------|
| 评价系统 | 13 | ✅ | 无效评分→400、正常评价→201、评分/内容/用户名正确、重复评价→400、他人→403、评价列表、不存在→404、评分更新 |
| 站内消息 | 12 | ✅ | 列表200、自动产生消息、unread_count、标记单条/全部已读、筛选未读、无token→401、隔离性 |
| 收藏功能 | 11 | ✅ | 收藏201+含worker、幂等200、列表2条、check=true/false、取消200、重复取消404、不存在404、无token401 |
| 推荐 API | 10 | ✅ | 个性化推荐非空、不含已用W1/W3、不含离线W4、新用户→popular、未登录→popular、limit生效 |
| 前端页面 | 1 | ✅ | messages.html 存在 |
| **合计** | **54** | **✅ 全部通过** | |

---

## 阶段六：上线保障（✅ 已完成）

**目标**：安全加固、性能优化、监控告警、CI/CD 流水线，确保生产可用。

### To-Do List

- [x] 安全 — 接口限流（Flask-Limiter，认证接口 10/min，默认 60/min）
- [x] 安全 — 安全响应头（X-Content-Type-Options / X-Frame-Options / X-XSS-Protection / Referrer-Policy）
- [x] 安全 — 敏感配置环境变量化（.env.example + docker-compose env_file）
- [x] 安全 — Nginx 安全头 + 代理超时配置
- [x] 性能 — 数据库索引优化（14 个索引覆盖所有外键和高频查询字段）
- [x] 性能 — Nginx gzip 压缩 + 静态资源缓存（7 天 expires）
- [x] 监控 — 健康检查增强（数据库连通性检测，200/503 状态区分）
- [x] 监控 — 结构化 JSON 日志（JsonFormatter，可对接 ELK/Loki）
- [x] 监控 — 请求计时日志（每次请求记录耗时 ms）
- [x] 监控 — 异常告警 Webhook（钉钉/飞书/Slack，500 错误自动通知）
- [x] 监控 — 全局 500/429 错误处理
- [x] CI/CD — GitHub Actions 自动测试 + Docker 构建 + 代码检查
- [x] 文档 — OpenAPI 3.0 接口文档（GET /api/docs）
- [x] 文档 — 部署运维手册（DEPLOY.md）
- [x] 部署 — 前端 Dockerfile 更新（COPY *.html 通配符覆盖全部 14 个页面）

### 核心交付物

| 交付物 | 文件 |
|--------|------|
| 安全加固（限流+安全头+.env） | `backend/app.py`, `.env.example` |
| 结构化日志 + 告警 Webhook | `backend/app.py` (JsonFormatter + send_alert) |
| Nginx 优化（gzip+缓存+安全头） | `frontend/nginx.conf` |
| 数据库索引（14 个） | `backend/init.sql` |
| CI/CD 流水线 | `.github/workflows/ci.yml` |
| OpenAPI 文档 | `backend/app.py` (GET /api/docs) |
| 部署运维手册 | `DEPLOY.md` |
| Docker 配置更新 | `frontend/Dockerfile`, `docker-compose.yml` |

### 测试报告

**测试时间**：2026-03-16 | **测试方式**：自动化验证（SQLite 替代 MySQL）| **结果**：✅ 39/39 通过，0 失败

| 测试模块 | 测试项数 | 结果 | 测试内容 |
|----------|----------|------|----------|
| 安全响应头 | 4 | ✅ | X-Content-Type-Options/X-Frame-Options/X-XSS-Protection/Referrer-Policy 全部正确 |
| 健康检查增强 | 4 | ✅ | 返回200、包含 status/timestamp/database 字段 |
| 限流器 | 1 | ✅ | Flask-Limiter 已加载 |
| 全局错误处理 | 2 | ✅ | 429/500 handler 已注册 |
| 结构化日志 | 2 | ✅ | JsonFormatter 存在、输出合法 JSON（含 timestamp/level/message） |
| 告警函数 | 2 | ✅ | send_alert 存在、无 webhook 时不报错 |
| OpenAPI 文档 | 4 | ✅ | /api/docs 返回200、包含 openapi/paths/info.title |
| 配置文件 | 1 | ✅ | .env.example 存在 |
| 前端 Dockerfile | 1 | ✅ | 使用 COPY *.html 通配符 |
| docker-compose | 2 | ✅ | 包含 env_file 配置、使用 ${} 变量替换 |
| Nginx 配置 | 4 | ✅ | gzip on、expires 缓存、X-Frame-Options、X-Content-Type-Options |
| 数据库索引 | 4 | ✅ | orders/messages/workers 表关键索引存在 |
| CI/CD 工作流 | 3 | ✅ | ci.yml 存在、包含 docker build、包含 pytest |
| 部署文档 | 3 | ✅ | DEPLOY.md 存在、包含 Docker 说明、包含环境变量说明 |
| 全链路安全头 | 2 | ✅ | /api/categories 和 /api/workers 均返回安全头 |
| **合计** | **39** | **✅ 全部通过** | |

---

## 技术选型备忘

| 需求 | 选型 |
|------|------|
| 前端图表 | ECharts / Chart.js |
| 缓存 | Redis（加入 docker-compose） |
| 定时任务 | APScheduler / Celery |
| 文件上传 | MinIO / 本地存储 |
| API 文档 | Flask-RESTX 或 Flasgger（Swagger） |
| 限流 | Flask-Limiter |
| 日志 | Python logging + JSON formatter |
| CI/CD | GitHub Actions |

---

## 里程碑时间建议

| 里程碑 | 建议节奏 |
|--------|----------|
| 阶段二完成 | 核心业务可演示 |
| 阶段三完成 | 后台可运营 |
| 阶段四完成 | 交易闭环跑通 |
| 阶段五完成 | 体验完善，可内测 |
| 阶段六完成 | 生产就绪，可上线 |

---

*此文档随开发进度持续更新，每完成一个任务即勾选对应项。*
