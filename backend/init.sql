CREATE DATABASE IF NOT EXISTS xiaxia_factory CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE xiaxia_factory;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(200) NOT NULL,
    role VARCHAR(20) DEFAULT 'user',
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 超级管理员账户 (密码: admin123456)
INSERT INTO users (username, email, password_hash, role, created_at)
VALUES ('admin', 'admin@xiaxia.factory', '$2b$12$cDbtbODl7aAN9jHNjlchkOGowo8ccvq8sPb2/Lug1wvLh3ap1doZK', 'admin', NOW())
ON DUPLICATE KEY UPDATE role='admin';

-- 分类表
CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    icon VARCHAR(100) NOT NULL DEFAULT 'mdi:briefcase',
    description VARCHAR(200) DEFAULT '',
    sort_order INT DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 数字员工表
CREATE TABLE IF NOT EXISTS workers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category_id INT NOT NULL,
    avatar_icon VARCHAR(100) DEFAULT 'mdi:robot-happy-outline',
    avatar_gradient_from VARCHAR(30) DEFAULT '#6A0DAD',
    avatar_gradient_to VARCHAR(30) DEFAULT '#00D2FF',
    level INT DEFAULT 5,
    skills TEXT DEFAULT NULL,
    description TEXT DEFAULT NULL,
    hourly_rate DECIMAL(10,2) NOT NULL,
    billing_unit VARCHAR(20) DEFAULT '时薪',
    status VARCHAR(20) DEFAULT 'online',
    rating DECIMAL(2,1) DEFAULT 5.0,
    total_orders INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 订单表
CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_no VARCHAR(30) NOT NULL UNIQUE,
    user_id INT NOT NULL,
    worker_id INT NOT NULL,
    duration_hours INT NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    remark TEXT DEFAULT NULL,
    paid_at DATETIME DEFAULT NULL,
    activated_at DATETIME DEFAULT NULL,
    completed_at DATETIME DEFAULT NULL,
    cancelled_at DATETIME DEFAULT NULL,
    refunded_at DATETIME DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (worker_id) REFERENCES workers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 支付记录表
CREATE TABLE IF NOT EXISTS payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    payment_no VARCHAR(40) NOT NULL UNIQUE,
    order_id INT NOT NULL,
    user_id INT NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    method VARCHAR(30) DEFAULT 'mock',
    status VARCHAR(20) DEFAULT 'success',
    paid_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    refunded_at DATETIME DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 评价表
CREATE TABLE IF NOT EXISTS reviews (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL UNIQUE,
    user_id INT NOT NULL,
    worker_id INT NOT NULL,
    rating INT NOT NULL,
    content TEXT DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (worker_id) REFERENCES workers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 站内消息表
CREATE TABLE IF NOT EXISTS messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(200) NOT NULL,
    content TEXT DEFAULT NULL,
    msg_type VARCHAR(30) DEFAULT 'system',
    related_order_id INT DEFAULT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 收藏表
CREATE TABLE IF NOT EXISTS favorites (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    worker_id INT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_worker (user_id, worker_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (worker_id) REFERENCES workers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ===== 性能索引 =====
CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_worker_id ON orders(worker_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_created_at ON orders(created_at);
CREATE INDEX idx_payments_order_id ON payments(order_id);
CREATE INDEX idx_payments_user_id ON payments(user_id);
CREATE INDEX idx_reviews_worker_id ON reviews(worker_id);
CREATE INDEX idx_reviews_user_id ON reviews(user_id);
CREATE INDEX idx_messages_user_id ON messages(user_id);
CREATE INDEX idx_messages_is_read ON messages(is_read);
CREATE INDEX idx_messages_created_at ON messages(created_at);
CREATE INDEX idx_favorites_user_id ON favorites(user_id);
CREATE INDEX idx_workers_category_id ON workers(category_id);
CREATE INDEX idx_workers_status ON workers(status);

-- ===== 种子数据：分类 =====
INSERT INTO categories (name, icon, description, sort_order) VALUES
('开发工程', 'mdi:code-braces', '全栈开发、后端架构、移动端、DevOps', 1),
('创意设计', 'mdi:palette', 'UI/UX设计、原画插画、3D建模', 2),
('智能客服', 'mdi:headphones', '多语言客服、投诉处理、智能应答', 3),
('数据分析', 'mdi:chart-areaspline', '数据挖掘、BI报表、金融分析', 4),
('内容运营', 'mdi:movie-edit', '短视频剪辑、文案撰写、社媒运营', 5),
('法务合规', 'mdi:gavel', '合同审核、知识产权、合规审查', 6),
('营销推广', 'mdi:search-web', 'SEO优化、广告投放、增长黑客', 7),
('游戏策划', 'mdi:controller', '数值策划、关卡设计、游戏测试', 8)
ON DUPLICATE KEY UPDATE name=name;

-- ===== 种子数据：数字员工（12位） =====
INSERT INTO workers (name, category_id, avatar_icon, avatar_gradient_from, avatar_gradient_to, level, skills, description, hourly_rate, billing_unit, status, rating, total_orders) VALUES
('全栈架构师 #001', 1, 'mdi:code-braces', '#6366f1', '#9333ea', 9, 'React,Node.js,Go,Kubernetes,微服务', '精通前后端分离架构，擅长高并发系统设计，具备10万+QPS生产系统调优经验。支持React/Vue/Angular前端及Go/Java/Python后端开发。', 1.80, '时薪', 'online', 4.9, 1842),
('Python全栈工程狮', 1, 'mdi:language-python', '#3b82f6', '#06b6d4', 8, 'Python,Django,FastAPI,PostgreSQL,Redis', '专注Python生态，从Web应用到数据管道全链路覆盖。熟练使用Django/FastAPI构建企业级应用，精通异步编程和性能优化。', 1.50, '时薪', 'online', 4.8, 1256),
('移动端开发专家', 1, 'mdi:cellphone-link', '#8b5cf6', '#ec4899', 7, 'Flutter,React Native,iOS,Android,跨平台', '一套代码多端运行，精通Flutter与React Native跨平台开发。具备原生iOS/Android开发经验，确保最佳用户体验。', 2.00, '时薪', 'online', 4.7, 893),
('Midjourney 原画师', 2, 'mdi:palette', '#ec4899', '#f43f5e', 7, '赛博朋克,写实风格,插画,概念设计', '精通多种AI绘画风格，擅长将抽象需求转化为视觉作品。单日可交付20+高质量原画，满足游戏、广告、品牌等多场景需求。', 0.50, '按件计费', 'online', 4.8, 3210),
('UI/UX 动效大师', 2, 'mdi:animation-play', '#f59e0b', '#ef4444', 8, 'Figma,After Effects,Lottie,交互设计', '专注用户体验和界面动效设计，将静态页面转化为流畅的交互体验。熟练使用Figma设计系统，支持Lottie动画导出。', 2.20, '时薪', 'busy', 4.9, 967),
('多语言客服 #12', 3, 'mdi:headphones', '#06b6d4', '#3b82f6', 8, '英语,日语,韩语,投诉处理,智能应答', '支持中英日韩四语实时对话，7×24小时不间断服务。内置情感分析引擎，智能识别客户情绪并调整应答策略，客户满意度4.9+。', 299.00, '月租', 'online', 4.9, 2100),
('智能质检客服', 3, 'mdi:shield-check', '#10b981', '#059669', 6, '质量检测,话术优化,工单流转', '实时监控客服对话质量，自动识别违规话术和服务漏洞。支持对接主流工单系统，自动生成质检报告和改进建议。', 199.00, '月租', 'online', 4.6, 580),
('金融分析师 Pro', 4, 'mdi:chart-areaspline', '#f59e0b', '#ea580c', 10, '波段分析,风险管理,量化策略,财报解读', '具备CFA级别的金融分析能力，擅长A股/美股/加密货币多市场分析。支持实时行情监控、风险预警和量化策略回测。', 5.20, '时薪', 'online', 4.9, 756),
('短视频剪辑手', 5, 'mdi:movie-edit', '#ef4444', '#ec4899', 6, '爆款节奏,字幕生成,转场特效,多平台适配', '精通抖音/快手/B站等平台的爆款视频节奏。一键生成字幕、添加转场特效，支持竖屏/横屏多尺寸输出，日产量50+条。', 0.95, '时薪', 'online', 4.5, 4320),
('法律文书合规官', 6, 'mdi:gavel', '#10b981', '#059669', 8, '合同审核,侵权检索,GDPR合规,知识产权', '基于最新法律数据库的智能合规审查，支持合同条款风险识别、知识产权侵权检索和GDPR合规检查。审核效率是人类律师的50倍。', 4.50, '时薪', 'online', 4.8, 1120),
('SEO 增长黑客', 7, 'mdi:search-web', '#8b5cf6', '#d946ef', 5, '关键词策略,文章生成,外链建设,数据追踪', '全链路SEO优化方案，从关键词调研到内容生产到排名追踪一站式服务。支持Google/百度/Bing多搜索引擎优化。', 0.12, '按件计费', 'online', 4.4, 6780),
('游戏数值策划师', 8, 'mdi:controller', '#0ea5e9', '#6366f1', 9, '概率模型,经济系统平衡,数值仿真,玩家行为分析', '精通游戏经济系统设计和数值平衡调优。基于蒙特卡洛模拟和玩家行为数据，确保游戏内经济不崩溃、数值不膨胀。', 3.20, '时薪', 'online', 4.7, 432)
ON DUPLICATE KEY UPDATE name=name;

-- ===== 迭代 A: 新增机器人商品与部署模型 =====

-- 扩展 workers 表: 新增 worker_type / delivery_mode / template_key
ALTER TABLE workers
    ADD COLUMN IF NOT EXISTS worker_type VARCHAR(20) DEFAULT 'generic',
    ADD COLUMN IF NOT EXISTS delivery_mode VARCHAR(20) DEFAULT 'manual',
    ADD COLUMN IF NOT EXISTS template_key VARCHAR(50) DEFAULT '';

-- 扩展 orders 表: 新增 order_type / service_plan_id
ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS order_type VARCHAR(20) DEFAULT 'rental',
    ADD COLUMN IF NOT EXISTS service_plan_id INT DEFAULT NULL;

-- 组织表
CREATE TABLE IF NOT EXISTS organizations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    owner_user_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    industry VARCHAR(50) DEFAULT '',
    status VARCHAR(20) DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Agent 模板表
CREATE TABLE IF NOT EXISTS agent_templates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    `key` VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    source_repo VARCHAR(200) DEFAULT '',
    source_path VARCHAR(200) DEFAULT '',
    prompt_template TEXT DEFAULT NULL,
    default_tools TEXT DEFAULT NULL,
    risk_level VARCHAR(20) DEFAULT 'low',
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 服务套餐表
CREATE TABLE IF NOT EXISTS service_plans (
    id INT AUTO_INCREMENT PRIMARY KEY,
    worker_id INT NOT NULL,
    name VARCHAR(50) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    billing_cycle VARCHAR(20) DEFAULT 'monthly',
    session_quota INT DEFAULT 500,
    knowledge_base_limit INT DEFAULT 1,
    channel_limit INT DEFAULT 1,
    seat_limit INT DEFAULT 1,
    features TEXT DEFAULT NULL,
    sort_order INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (worker_id) REFERENCES workers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 部署实例表
CREATE TABLE IF NOT EXISTS deployments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    organization_id INT DEFAULT NULL,
    order_id INT NOT NULL,
    user_id INT NOT NULL,
    worker_id INT NOT NULL,
    template_id INT DEFAULT NULL,
    service_plan_id INT DEFAULT NULL,
    status VARCHAR(20) DEFAULT 'pending_setup',
    deployment_name VARCHAR(100) DEFAULT '',
    channel_type VARCHAR(30) DEFAULT 'web_chat',
    config_json TEXT DEFAULT NULL,
    embed_code TEXT DEFAULT NULL,
    started_at DATETIME DEFAULT NULL,
    suspended_at DATETIME DEFAULT NULL,
    expires_at DATETIME DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (worker_id) REFERENCES workers(id),
    FOREIGN KEY (template_id) REFERENCES agent_templates(id),
    FOREIGN KEY (service_plan_id) REFERENCES service_plans(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ===== 迭代 B: 知识库与会话体系 =====

-- 知识库表
CREATE TABLE IF NOT EXISTS knowledge_bases (
    id INT AUTO_INCREMENT PRIMARY KEY,
    deployment_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'draft',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (deployment_id) REFERENCES deployments(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 知识库文档表
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    knowledge_base_id INT NOT NULL,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    doc_type VARCHAR(20) DEFAULT 'faq',
    status VARCHAR(20) DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 会话表
CREATE TABLE IF NOT EXISTS conversation_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    deployment_id INT NOT NULL,
    visitor_id VARCHAR(100) DEFAULT '',
    visitor_name VARCHAR(100) DEFAULT '访客',
    status VARCHAR(20) DEFAULT 'active',
    satisfaction_score INT DEFAULT NULL,
    message_count INT DEFAULT 0,
    resolved BOOLEAN DEFAULT FALSE,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    ended_at DATETIME DEFAULT NULL,
    FOREIGN KEY (deployment_id) REFERENCES deployments(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 会话消息表
CREATE TABLE IF NOT EXISTS conversation_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id INT NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    confidence DECIMAL(3,2) DEFAULT NULL,
    source_doc_ids TEXT DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES conversation_sessions(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 转人工工单表
CREATE TABLE IF NOT EXISTS handoff_tickets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id INT NOT NULL,
    deployment_id INT NOT NULL,
    reason VARCHAR(200) DEFAULT '',
    status VARCHAR(20) DEFAULT 'pending',
    assigned_to VARCHAR(100) DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    resolved_at DATETIME DEFAULT NULL,
    FOREIGN KEY (session_id) REFERENCES conversation_sessions(id),
    FOREIGN KEY (deployment_id) REFERENCES deployments(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 用量记录表
CREATE TABLE IF NOT EXISTS usage_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    deployment_id INT NOT NULL,
    record_date DATE NOT NULL,
    session_count INT DEFAULT 0,
    message_count INT DEFAULT 0,
    handoff_count INT DEFAULT 0,
    resolved_count INT DEFAULT 0,
    avg_satisfaction DECIMAL(3,2) DEFAULT NULL,
    FOREIGN KEY (deployment_id) REFERENCES deployments(id),
    UNIQUE KEY uq_deploy_date (deployment_id, record_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ===== 新增索引 =====
CREATE INDEX idx_deployments_user_id ON deployments(user_id);
CREATE INDEX idx_deployments_status ON deployments(status);
CREATE INDEX idx_deployments_order_id ON deployments(order_id);
CREATE INDEX idx_kb_deployment_id ON knowledge_bases(deployment_id);
CREATE INDEX idx_kb_docs_kb_id ON knowledge_documents(knowledge_base_id);
CREATE INDEX idx_kb_docs_status ON knowledge_documents(status);
CREATE INDEX idx_sessions_deployment_id ON conversation_sessions(deployment_id);
CREATE INDEX idx_sessions_status ON conversation_sessions(status);
CREATE INDEX idx_messages_session_id ON conversation_messages(session_id);
CREATE INDEX idx_handoff_deployment_id ON handoff_tickets(deployment_id);
CREATE INDEX idx_handoff_status ON handoff_tickets(status);
CREATE INDEX idx_usage_deployment_id ON usage_records(deployment_id);

-- ===== 种子数据: Agent Template =====
INSERT INTO agent_templates (`key`, name, source_repo, source_path, prompt_template, default_tools, risk_level) VALUES
('support_responder', '智能客服助手 (Support Responder)',
 'https://github.com/msitarzewski/agency-agents',
 'support/support-support-responder.md',
 '你是一个专业的客服助手，擅长多渠道客户服务、问题解决和用户体验优化。你始终保持同理心、专注于解决方案、主动为客户着想。',
 '["knowledge_search","handoff","session_close"]',
 'low')
ON DUPLICATE KEY UPDATE name=name;

-- ===== 更新种子员工: 客服员工标记为 agent 类型 =====
UPDATE workers SET worker_type='agent', delivery_mode='semi_auto', template_key='support_responder'
WHERE name IN ('多语言客服 #12', '智能质检客服');

-- ===== 种子数据: 虾虾客服员工 Pro（新增旗舰客服机器人） =====
INSERT INTO workers (name, category_id, avatar_icon, avatar_gradient_from, avatar_gradient_to, level, skills, description, hourly_rate, billing_unit, status, rating, total_orders, worker_type, delivery_mode, template_key) VALUES
('虾虾客服员工 Pro', 3, 'mdi:robot-happy', '#2563eb', '#7c3aed', 9,
 '7x24在线,知识库问答,智能转人工,多语言,会话报表,品牌定制',
 '虾虾工厂旗舰数字客服员工。基于 Support Responder 技术，支持网页聊天窗口接入，可上传企业知识库实现智能问答。置信度不足时自动转人工，支持会话记录、满意度统计和运营报表。适合中小 SaaS 团队、电商商家和 B 端企业官网。\n\n核心能力：\n• 7×24 小时在线自动应答\n• 上传 FAQ / 产品文档 / 售后政策\n• 配置品牌语气和禁答规则\n• 低置信度自动转人工\n• 实时会话监控和数据报表\n\n首发场景：网页在线客服 + 知识库问答 + 转人工',
 0, '月租', 'online', 5.0, 0, 'agent', 'semi_auto', 'support_responder')
ON DUPLICATE KEY UPDATE description=VALUES(description);

-- ===== 种子数据: 服务套餐（绑定虾虾客服员工 Pro） =====
-- 注意: 以下使用子查询获取 worker_id
INSERT INTO service_plans (worker_id, name, price, billing_cycle, session_quota, knowledge_base_limit, channel_limit, seat_limit, features, sort_order) VALUES
((SELECT id FROM workers WHERE name='虾虾客服员工 Pro' LIMIT 1),
 'Starter', 299.00, 'monthly', 500, 1, 1, 1,
 '["7x24在线客服","1个知识库","500次/月会话","1个网站渠道","人工接管入口","基础数据报表"]',
 1),
((SELECT id FROM workers WHERE name='虾虾客服员工 Pro' LIMIT 1),
 'Pro', 799.00, 'monthly', 3000, 3, 3, 5,
 '["7x24在线客服","3个知识库","3000次/月会话","3个渠道","5个人工坐席","会话报表","敏感词过滤","品牌语气定制","优先技术支持"]',
 2),
((SELECT id FROM workers WHERE name='虾虾客服员工 Pro' LIMIT 1),
 'Enterprise', 2999.00, 'monthly', 20000, 10, 10, 20,
 '["7x24在线客服","10个知识库","20000次/月会话","10个渠道","20个坐席","API接入","SSO单点登录","审计日志","SLA保障","专属客户经理","定制渠道连接器"]',
 3)
ON DUPLICATE KEY UPDATE name=name;
