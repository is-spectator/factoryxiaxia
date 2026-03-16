# 虾虾工厂 — 系统实现计划

> 数字员工租赁平台 · 分阶段交付路线图

---

## 当前进度总览

| 阶段 | 状态 | 说明 |
|------|------|------|
| 阶段一：基础骨架 | ✅ 已完成 | 官网 + 用户系统 + Docker 部署 |
| 阶段二：核心业务 | ✅ 已完成 | 数字员工目录 + 租赁流程 |
| 阶段三：管理后台 | ✅ 已完成 | 权限模型 + 数据看板 + CRUD 管理 |
| 阶段三：管理后台 | ⬜ 待开始 | 运营管理 + 数据看板 |
| 阶段四：支付与订单 | ⬜ 待开始 | 支付集成 + 订单生命周期 |
| 阶段五：增值功能 | ⬜ 待开始 | 评价 + 消息 + 推荐 |
| 阶段六：上线保障 | ⬜ 待开始 | 安全加固 + 监控 + CI/CD |

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

- [ ] 订单状态机设计（pending → paid → active → completed / refunded / cancelled）
- [ ] 支付接口抽象层（方便后续接入支付宝/微信支付）
- [ ] API — 模拟支付（POST /api/orders/:id/pay，开发环境用）
- [ ] API — 取消订单（POST /api/orders/:id/cancel）
- [ ] API — 申请退款（POST /api/orders/:id/refund）
- [ ] API — 确认完成（POST /api/orders/:id/complete）
- [ ] 前端 — 支付确认页（pay.html — 展示订单摘要、支付按钮）
- [ ] 前端 — 订单状态流转可视化（进度条/时间线组件）
- [ ] 支付回调处理 + 幂等性保证
- [ ] 订单超时自动取消（后台定时任务）
- [ ] 数据库 — 支付记录表（payments）

### 核心交付物

| 交付物 | 说明 |
|--------|------|
| 完整订单生命周期 | 6 种状态流转，前端可视化 |
| 支付模块 | 抽象层 + 模拟支付（可扩展真实支付） |
| 退款流程 | 用户申请 → 管理员审核 → 退款 |
| 定时任务 | 超时未支付订单自动取消 |

---

## 阶段五：增值功能

**目标**：提升用户体验和平台粘性 — 评价系统、站内消息、智能推荐。

### To-Do List

- [ ] 评价模型（reviews 表：订单ID、评分、评价内容、创建时间）
- [ ] API — 提交评价（POST /api/orders/:id/review）
- [ ] API — 查看员工评价（GET /api/workers/:id/reviews）
- [ ] 前端 — 评价组件（星级评分 + 文字评价）
- [ ] 消息模型（messages 表：发送者、接收者、内容、已读状态）
- [ ] API — 站内通知（GET /api/messages，订单状态变更自动通知）
- [ ] 前端 — 消息中心页（messages.html — 通知列表、已读/未读）
- [ ] 前端 — 顶栏消息小红点
- [ ] 推荐算法 — 基于用户历史订单推荐相似员工
- [ ] API — 推荐员工（GET /api/recommendations）
- [ ] 前端 — 首页推荐模块（"为你推荐"卡片区）
- [ ] 用户收藏功能（POST/DELETE /api/favorites/:worker_id）

### 核心交付物

| 交付物 | 说明 |
|--------|------|
| 评价系统 | 订单完成后可评分 + 评论，影响员工评分 |
| 站内消息 | 系统通知 + 消息中心 |
| 智能推荐 | 基于历史行为的员工推荐 |
| 收藏功能 | 用户可收藏/取消收藏数字员工 |

---

## 阶段六：上线保障

**目标**：安全加固、性能优化、监控告警、CI/CD 流水线，确保生产可用。

### To-Do List

- [ ] 安全 — 接口限流（Flask-Limiter）
- [ ] 安全 — CSRF 防护
- [ ] 安全 — SQL 注入 & XSS 防护审计
- [ ] 安全 — 敏感配置环境变量化（.env 文件 + docker-compose 读取）
- [ ] 安全 — HTTPS 证书配置（Let's Encrypt + Nginx）
- [ ] 性能 — 数据库索引优化
- [ ] 性能 — 静态资源 CDN / 压缩
- [ ] 性能 — API 响应缓存（Redis）
- [ ] 监控 — 健康检查增强（数据库连通性、内存/CPU）
- [ ] 监控 — 日志结构化输出 + 日志收集
- [ ] 监控 — 异常报警（邮件/钉钉 Webhook）
- [ ] CI/CD — GitHub Actions 自动测试
- [ ] CI/CD — 自动构建 Docker 镜像
- [ ] CI/CD — 自动部署到服务器
- [ ] 单元测试 — 核心 API 测试覆盖率 > 80%
- [ ] 文档 — API 接口文档（Swagger / OpenAPI）
- [ ] 文档 — 部署运维手册

### 核心交付物

| 交付物 | 说明 |
|--------|------|
| 安全加固 | 限流、CSRF、XSS/SQLi 防护、HTTPS |
| Redis 缓存层 | 热点数据缓存，提升响应速度 |
| CI/CD 流水线 | 提交 → 测试 → 构建 → 部署全自动 |
| 监控告警 | 健康检查 + 结构化日志 + 异常通知 |
| 测试套件 | 核心 API 单元测试 > 80% 覆盖率 |
| API 文档 | Swagger UI 在线文档 |

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
