# 0319 空空（KongKong）官方员工改造计划

> 日期：2026-03-19
> 项目：虾虾工厂 / `factoryxiaxia`
> 新增官方员工：`空空`
> 目标：把 `空空` 做成“购买后自动交付独立 OpenClaw 实例”的官方员工商品

---

## 一、产品定义

`空空` 不是普通问答型数字员工，而是一个“托管运行环境型官方员工”。

用户购买 `空空` 后，平台会：

1. 为该用户创建一份独立实例
2. 在独立容器中安装并运行 `OpenClaw`
3. 为该实例注入模型配置
4. 给用户交付一个专属的 OpenClaw 入口链接

一句话定义：

`空空 = 可购买的官方数字员工商品 + 每用户独占的 OpenClaw 容器实例 + 专属工作台入口`

---

## 二、架构决策

### 2.1 运行隔离：选择 Docker，不选轻量 sandbox

结论：首版采用 `Docker 容器`，不采用我们现有机器人配置式 sandbox。

原因：

- OpenClaw 官方本身就提供 Docker 部署路径和官方容器镜像，适合做托管运行
- 需求是“每个用户购买后实例化一份”，这是标准容器生命周期管理问题
- 需要用户间强隔离，容器比进程级 sandbox 更适合做资源限制、网络隔离、卷隔离和销毁回收
- 后续还要支持重启、暂停、续费、过期销毁、日志、监控，这些都更适合容器编排

首版不做 Kubernetes，先用单机 Docker Runtime + 平台编排即可。

### 2.2 交付入口：给用户一个“平台代理后的 OpenClaw 链接”

不直接把容器的 `18789` 端口裸露给公网。

首版交付方式：

- 每个实例分配一个平台侧入口
- 推荐 URL 形态：
  - `https://kongkong-<instance_slug>.agents.xiaxia.factory/`
- 或者如果证书/泛域名未就绪，退化为：
  - `https://app.xiaxia.factory/kongkong/<instance_slug>/`

平台必须作为反向代理和访问控制层，不能让用户直接连 Docker 容器原始端口。

### 2.3 模型接入：以你要求为准，但实现前要做兼容验证

你要求：

- Provider：Qwen DashScope
- 模型：`qwen-max`
- API key：使用你提供的 DashScope key

计划原则：

- 平台会把该 key 作为服务端 secret 注入实例环境，不写入代码仓库、不写入数据库明文
- `空空` 创建时默认把 OpenClaw 的主模型配置到 Qwen / DashScope

注意：

- 我在 2026-03-19 查了 OpenClaw 官方文档，OpenClaw 官方已支持 Alibaba `Model Studio` provider，文档里给的是 `modelstudio` / `MODELSTUDIO_API_KEY`，并注明是 OpenAI-compatible API
- 官方 Qwen provider 文档更偏 `qwen-portal` OAuth，而不是直接讲 DashScope API key

所以实现阶段必须先验证下面二选一哪条能稳定跑通：

1. 直接用 OpenClaw 官方 `modelstudio` provider 接 Alibaba / DashScope 兼容接口
2. 走 OpenClaw 自定义 OpenAI-compatible provider，把 DashScope `qwen-max` 接进去

上线门槛：

- 只有实际 smoke test 证明 `空空` 容器里的 OpenClaw 能稳定调用 `qwen-max`，这个 SKU 才能对外销售

---

## 三、实例隔离设计

每个购买 `空空` 的用户都会得到一份独立实例，隔离粒度如下：

### 3.1 容器隔离

- 1 个用户实例 = 1 个 OpenClaw Gateway 容器
- 容器命名示例：
  - `kongkong-<deployment_id>`
- 独立容器生命周期：
  - create
  - start
  - stop
  - restart
  - suspend
  - destroy

### 3.2 存储隔离

- 每个实例一个独立 volume / workspace 目录
- 路径示例：
  - `/var/lib/xiaxia/kongkong/<instance_id>/config`
  - `/var/lib/xiaxia/kongkong/<instance_id>/workspace`
  - `/var/lib/xiaxia/kongkong/<instance_id>/logs`

### 3.3 网络隔离

- 每个实例只暴露内部端口给平台反向代理
- 不给外部直接映射独立随机宿主机端口
- 平台网关按 `instance_slug` 反向代理到实例内部地址

### 3.4 凭证隔离

- 每个实例单独保存 OpenClaw dashboard token / pairing token
- 通过平台侧“短时 launch token”换取访问，不直接在前端暴露长期管理 token
- DashScope key 首版可平台统一托管，但后续建议升级为实例级 secret 引用

### 3.5 资源隔离

- 每个实例配置 CPU / 内存 / PIDs 限额
- 建议首版默认：
  - CPU: `1`
  - Memory: `2G`
  - PIDs limit: `256`
- 防止单个实例拖垮宿主机

---

## 四、系统改造范围

## 4.1 新商品与订单链路

- 新增官方员工：`空空`
- `worker_type` 仍归类为官方数字员工，但需要增加“运行环境型员工”标记
- 服务套餐需要和普通客服机器人分开
- 用户购买 `空空` 后，订单完成支付/确认收款时，不再只生成普通 deployment，而是生成 runtime instance

建议新增字段：

- `workers.runtime_kind = "openclaw_managed"`
- `service_plans.instance_type`
- `service_plans.cpu_limit`
- `service_plans.memory_limit_mb`
- `service_plans.storage_limit_gb`

## 4.2 新运行时模型

建议新增一张运行时实例表：

- `kongkong_instances`

建议字段：

- `id`
- `deployment_id`
- `user_id`
- `organization_id`
- `status`：`provisioning/running/stopped/suspended/error/destroyed`
- `container_name`
- `container_id`
- `instance_slug`
- `internal_port`
- `entry_url`
- `dashboard_token_encrypted`
- `model_provider`
- `model_name`
- `secret_ref`
- `workspace_path`
- `config_path`
- `logs_path`
- `cpu_limit`
- `memory_limit_mb`
- `storage_limit_gb`
- `last_heartbeat_at`
- `started_at`
- `stopped_at`
- `expires_at`
- `error_message`
- `created_at`

## 4.3 运行编排服务

建议新增服务层：

- `backend/services/kongkong_runtime_service.py`
- `backend/services/kongkong_provision_service.py`
- `backend/services/kongkong_proxy_service.py`

职责拆分：

- `runtime_service`
  - 创建/启动/停止/重启/销毁容器
- `provision_service`
  - 写配置文件
  - 注入模型 provider
  - 初始化 OpenClaw 工作目录
  - 获取 dashboard token
- `proxy_service`
  - 生成 launch link
  - 校验访问 token
  - 管理入口链接

## 4.4 网关与入口

建议新增一个面向 `空空` 的入口层：

- 平台 API：
  - `POST /api/kongkong/instances`
  - `GET /api/kongkong/instances`
  - `GET /api/kongkong/instances/:id`
  - `POST /api/kongkong/instances/:id/start`
  - `POST /api/kongkong/instances/:id/stop`
  - `POST /api/kongkong/instances/:id/restart`
  - `POST /api/kongkong/instances/:id/suspend`
  - `POST /api/kongkong/instances/:id/destroy`
  - `POST /api/kongkong/instances/:id/launch-link`

Launch link 方案：

- 平台生成 5 分钟有效的一次性签名 token
- 用户点击“进入空空工作台”
- 请求到平台代理层
- 平台校验 token 后转发到 OpenClaw dashboard

首版不要把 OpenClaw 自己的原始 dashboard token 直接展示给用户。

---

## 五、OpenClaw 镜像策略

### 5.1 首版镜像方案

做一层官方镜像包装：

- 基础镜像优先使用 OpenClaw 官方镜像或官方 Dockerfile 构建结果
- 我们再封装一层：
  - 预置必须的环境变量模板
  - 预置默认工作目录
  - 预置模型配置写入脚本
  - 预置健康检查脚本

建议镜像名：

- `xiaxia/kongkong-openclaw:<version>`

### 5.2 首版容器内容

容器内至少包含：

- OpenClaw gateway
- OpenClaw CLI
- 模型配置初始化脚本
- 健康检查脚本
- 日志输出目录

首版不做复杂浏览器自动化插件预装，只做“稳定工作台 + 模型可用 + 基础会话可用”。

---

## 六、Qwen / DashScope 配置计划

### 6.1 原则

- 使用你提供的 key，但只写入服务端 secret，不写入仓库
- 不把真实 key 记录到 `0319_kongkong_todo.md`
- 运行时由平台把 secret 注入容器

### 6.2 首版配置目标

目标配置：

- provider: `dashscope` 或 `modelstudio`（以兼容验证结果为准）
- primary model: `qwen-max`
- fallback: 可以暂时留空，或后续补 `qwen-plus`

### 6.3 必做验证

实现阶段第一优先验证项：

1. 在独立容器里启动 OpenClaw
2. 注入 DashScope / Alibaba 配置
3. 执行 OpenClaw 模型状态检查
4. 通过工作台或 CLI 发一条消息
5. 确认实际返回来自 Qwen

如果官方 `modelstudio` provider 不支持 `qwen-max` 这个模型名，则需要立即切到：

- 自定义 OpenAI-compatible provider
- 或者与你确认改为 `qwen3-max`

这个问题必须在编码前半天内验证完，不然会影响整条链路。

---

## 七、迭代计划

## Phase A：技术验证（P0）

目标：证明 OpenClaw 能在我们托管容器里跑起来，并接上 Qwen。

任务：

- [ ] 拉取 OpenClaw 官方镜像/源码，验证 Docker 路径
- [ ] 验证 OpenClaw dashboard 默认端口、token 和 pairing 流程
- [ ] 验证 Alibaba / DashScope 模型接入方式
- [ ] 验证 `qwen-max` 是否能被 OpenClaw 正常识别
- [ ] 选定最终 provider 写法：`modelstudio` 还是 custom provider
- [ ] 产出最小启动命令、环境变量清单、健康检查方式

交付物：

- `kongkong_architecture.md`
- 最小可运行容器 PoC
- Qwen smoke test 记录

验收标准：

- 本地单容器启动 OpenClaw 成功
- 可以得到 dashboard 入口
- 可以发出一条真实 Qwen 回复

## Phase B：商品与数据模型（P0）

目标：把 `空空` 接到现有购买/部署系统里。

任务：

- [ ] 新增官方员工 `空空`
- [ ] 新增套餐与资源配额字段
- [ ] 新增 `kongkong_instances` 表
- [ ] 下单后生成 `deployment + kongkong_instance`
- [ ] 把 `空空` 从普通客服型员工中区分出来

交付物：

- 数据模型迁移
- 后端下单/创建实例接口
- 后台管理基础字段

验收标准：

- 用户购买 `空空` 后，后台能看到对应 runtime instance 记录

## Phase C：容器编排与实例化（P0）

目标：购买后自动起容器。

任务：

- [ ] 封装 `docker create/start/stop/rm` 服务
- [ ] 生成实例目录、配置目录、日志目录
- [ ] 把 OpenClaw 配置写入实例目录
- [ ] 注入模型 provider 和 secret
- [ ] 起容器后探活
- [ ] 失败时回写错误状态

交付物：

- `kongkong_runtime_service.py`
- 容器实例化接口
- 健康检查逻辑

验收标准：

- 用户购买后能在 1-3 分钟内得到 `running` 状态实例

## Phase D：入口链接与访问控制（P0）

目标：给用户一个可登录的 OpenClaw 工作台链接。

任务：

- [ ] 新增 launch-link API
- [ ] 新增短时签名 token
- [ ] 平台侧代理到实例 dashboard
- [ ] 支持首次访问和刷新访问
- [ ] 记录最近访问时间和来源 IP
- [ ] 未登录、越权、过期 token 都要拒绝

交付物：

- `GET/POST launch-link` 接口
- 网关代理配置
- 前端“进入空空工作台”按钮

验收标准：

- 用户从订单页或“我的机器人”点击后，能进入自己的 OpenClaw
- 不能打开别人的实例

## Phase E：用户隔离与安全（P0）

目标：确保一个用户的空空不会影响另一个用户。

任务：

- [ ] 独立容器名、独立卷、独立工作目录
- [ ] 独立 dashboard token
- [ ] 独立反向代理路由
- [ ] CPU / Memory / PIDs 限制
- [ ] 禁止把 Docker socket 暴露给用户实例
- [ ] 禁止实例间互相访问
- [ ] 审计实例创建、启动、重启、销毁、访问入口

交付物：

- 安全配置
- 审计日志
- 实例隔离说明

验收标准：

- A 用户实例停止/异常，不影响 B 用户实例
- A 用户拿不到 B 用户入口

## Phase F：控制台与运营（P1）

目标：让平台能卖、能管、能排障。

任务：

- [ ] 订单详情展示 `空空` 实例状态
- [ ] “我的机器人”增加 `空空工作台入口`
- [ ] 后台支持重启、暂停、恢复、销毁
- [ ] 后台展示实例最近错误信息
- [ ] 展示入口链接状态、最近访问、过期时间
- [ ] 到期实例自动停机并回收

交付物：

- 前端控制台页
- 管理后台动作按钮
- 到期回收脚本

验收标准：

- 运营能处理用户反馈，不需要手工 SSH 宿主机

---

## 八、上线前验收脚本

必须验证这条完整链路：

1. 用户搜索到 `空空`
2. 用户完成购买 / 付款确认
3. 系统自动创建 `kongkong_instance`
4. 系统自动拉起独立 OpenClaw 容器
5. 用户在订单页看到“进入空空工作台”
6. 点击后进入自己的 OpenClaw 工作台
7. 在工作台里发一条消息，确认实际走 Qwen
8. 再购买第二个用户实例，验证两个实例互不影响
9. 暂停 A 用户实例，确认 B 用户实例不受影响
10. 销毁 A 用户实例，确认入口链接失效

---

## 九、最大风险点

### R1：OpenClaw 与 DashScope `qwen-max` 的 provider 兼容性

这是当前最大技术风险。

解决策略：

- 第一步先做 smoke test
- 如果官方 `modelstudio` 不能稳定跑 `qwen-max`
- 立刻改用 OpenAI-compatible custom provider
- 如果仍不稳定，再与你确认改成官方支持更明确的 `qwen3-max`

### R2：OpenClaw dashboard 的 token / pairing 机制

OpenClaw 默认更偏“个人设备自托管”，我们现在要把它托管成平台商品。

解决策略：

- 首版不直接暴露底层 token
- 由平台签发 launch link
- 后续再考虑更深的 SSO 封装

### R3：反向代理 WebSocket / 长连接兼容

OpenClaw 工作台大概率需要稳定的长连接和 token 交互。

解决策略：

- 反向代理层提前做 WebSocket 支持
- 专门做一次浏览器走查和刷新/重连测试

### R4：容器启动时延

如果容器每次创建都很慢，购买体验会差。

解决策略：

- 预构建镜像
- 首版接受 1-3 分钟 provisioning
- 后续再做 warm pool

---

## 十、建议执行顺序

1. 先做 `Phase A 技术验证`
2. 验证通过后再做 `Phase B + C`
3. 然后做 `Phase D` 交付入口
4. 最后补 `Phase E + F`

只有 `Phase A` 验证通过，`空空` 才值得继续往商品化方向开发。

---

## 十一、外部参考

- OpenClaw 官方仓库：
  - [https://github.com/openclaw/openclaw](https://github.com/openclaw/openclaw)
- OpenClaw Docker 文档：
  - [https://docs.openclaw.ai/install/docker](https://docs.openclaw.ai/install/docker)
- OpenClaw Models / Provider 文档：
  - [https://docs.openclaw.ai/concepts/models](https://docs.openclaw.ai/concepts/models)
- OpenClaw Alibaba Model Studio Provider：
  - [https://docs.openclaw.ai/providers/modelstudio](https://docs.openclaw.ai/providers/modelstudio)
- OpenClaw Qwen Provider：
  - [https://docs.openclaw.ai/providers/qwen](https://docs.openclaw.ai/providers/qwen)
