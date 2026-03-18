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

CREATE TABLE IF NOT EXISTS organizations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    owner_user_id INT NOT NULL,
    name VARCHAR(120) NOT NULL,
    industry VARCHAR(80) DEFAULT '',
    status VARCHAR(20) DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS agent_templates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    `key` VARCHAR(80) NOT NULL UNIQUE,
    name VARCHAR(120) NOT NULL,
    source_repo VARCHAR(255) DEFAULT '',
    source_path VARCHAR(255) DEFAULT '',
    prompt_template TEXT DEFAULT NULL,
    default_tools TEXT DEFAULT NULL,
    risk_level VARCHAR(20) DEFAULT 'medium',
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
    worker_type VARCHAR(30) DEFAULT 'general',
    delivery_mode VARCHAR(30) DEFAULT 'manual_service',
    template_key VARCHAR(80) DEFAULT NULL,
    rating DECIMAL(2,1) DEFAULT 5.0,
    total_orders INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS service_plans (
    id INT AUTO_INCREMENT PRIMARY KEY,
    worker_id INT NOT NULL,
    slug VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(255) DEFAULT '',
    billing_cycle VARCHAR(20) DEFAULT 'monthly',
    price DECIMAL(10,2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'CNY',
    included_conversations INT DEFAULT 500,
    max_handoffs INT DEFAULT 50,
    channel_limit INT DEFAULT 1,
    seat_limit INT DEFAULT 1,
    default_duration_hours INT DEFAULT 720,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_worker_plan_slug (worker_id, slug),
    FOREIGN KEY (worker_id) REFERENCES workers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 订单表
CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_no VARCHAR(30) NOT NULL UNIQUE,
    user_id INT NOT NULL,
    worker_id INT NOT NULL,
    service_plan_id INT DEFAULT NULL,
    duration_hours INT NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    order_type VARCHAR(30) DEFAULT 'rental',
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
    FOREIGN KEY (worker_id) REFERENCES workers(id),
    FOREIGN KEY (service_plan_id) REFERENCES service_plans(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS deployments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    organization_id INT NOT NULL,
    order_id INT NOT NULL UNIQUE,
    user_id INT NOT NULL,
    worker_id INT NOT NULL,
    template_id INT NOT NULL,
    service_plan_id INT DEFAULT NULL,
    status VARCHAR(30) DEFAULT 'pending_setup',
    deployment_name VARCHAR(120) NOT NULL,
    channel_type VARCHAR(30) DEFAULT 'web_widget',
    config_json TEXT DEFAULT NULL,
    started_at DATETIME DEFAULT NULL,
    suspended_at DATETIME DEFAULT NULL,
    expires_at DATETIME DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (worker_id) REFERENCES workers(id),
    FOREIGN KEY (template_id) REFERENCES agent_templates(id),
    FOREIGN KEY (service_plan_id) REFERENCES service_plans(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS knowledge_bases (
    id INT AUTO_INCREMENT PRIMARY KEY,
    deployment_id INT NOT NULL,
    name VARCHAR(120) NOT NULL,
    description VARCHAR(255) DEFAULT '',
    status VARCHAR(20) DEFAULT 'draft',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    published_at DATETIME DEFAULT NULL,
    FOREIGN KEY (deployment_id) REFERENCES deployments(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS knowledge_documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    knowledge_base_id INT NOT NULL,
    title VARCHAR(160) NOT NULL,
    doc_type VARCHAR(30) DEFAULT 'faq',
    source_name VARCHAR(160) DEFAULT '',
    content TEXT NOT NULL,
    char_count INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'draft',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS conversation_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    deployment_id INT NOT NULL,
    visitor_name VARCHAR(120) DEFAULT '',
    visitor_contact VARCHAR(160) DEFAULT '',
    channel_type VARCHAR(30) DEFAULT 'web_widget',
    status VARCHAR(30) DEFAULT 'open',
    last_confidence DECIMAL(4,3) DEFAULT NULL,
    needs_handoff BOOLEAN DEFAULT FALSE,
    handoff_reason VARCHAR(255) DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (deployment_id) REFERENCES deployments(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS conversation_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id INT NOT NULL,
    role VARCHAR(20) DEFAULT 'user',
    content TEXT NOT NULL,
    confidence DECIMAL(4,3) DEFAULT NULL,
    risk_level VARCHAR(20) DEFAULT 'low',
    source_refs_json TEXT DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES conversation_sessions(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS handoff_tickets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    deployment_id INT NOT NULL,
    session_id INT NOT NULL,
    user_id INT NOT NULL,
    ticket_no VARCHAR(40) NOT NULL UNIQUE,
    status VARCHAR(20) DEFAULT 'open',
    reason VARCHAR(255) DEFAULT '',
    summary TEXT DEFAULT NULL,
    request_source VARCHAR(20) DEFAULT 'system',
    resolved_at DATETIME DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (deployment_id) REFERENCES deployments(id),
    FOREIGN KEY (session_id) REFERENCES conversation_sessions(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS usage_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    deployment_id INT NOT NULL,
    session_id INT DEFAULT NULL,
    metric_type VARCHAR(30) NOT NULL,
    quantity DECIMAL(10,2) DEFAULT 1,
    unit VARCHAR(20) DEFAULT 'count',
    meta_json TEXT DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (deployment_id) REFERENCES deployments(id),
    FOREIGN KEY (session_id) REFERENCES conversation_sessions(id)
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
CREATE INDEX idx_orders_service_plan_id ON orders(service_plan_id);
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
CREATE INDEX idx_workers_worker_type ON workers(worker_type);
CREATE INDEX idx_service_plans_worker_id ON service_plans(worker_id);
CREATE INDEX idx_deployments_user_id ON deployments(user_id);
CREATE INDEX idx_deployments_status ON deployments(status);
CREATE INDEX idx_knowledge_bases_deployment_id ON knowledge_bases(deployment_id);
CREATE INDEX idx_knowledge_documents_knowledge_base_id ON knowledge_documents(knowledge_base_id);
CREATE INDEX idx_knowledge_documents_status ON knowledge_documents(status);
CREATE INDEX idx_conversation_sessions_deployment_id ON conversation_sessions(deployment_id);
CREATE INDEX idx_conversation_sessions_status ON conversation_sessions(status);
CREATE INDEX idx_conversation_messages_session_id ON conversation_messages(session_id);
CREATE INDEX idx_handoff_tickets_deployment_id ON handoff_tickets(deployment_id);
CREATE INDEX idx_handoff_tickets_status ON handoff_tickets(status);
CREATE INDEX idx_usage_records_deployment_id ON usage_records(deployment_id);
CREATE INDEX idx_usage_records_metric_type ON usage_records(metric_type);

INSERT INTO agent_templates (`key`, name, source_repo, source_path, prompt_template, default_tools, risk_level, is_active)
VALUES (
    'support_responder',
    'Support Responder',
    'https://github.com/msitarzewski/agency-agents',
    'support/support-support-responder.md',
    '你是企业专属数字客服员工，负责基于知识库进行客户问答、问题澄清、工单分流与转人工判断。回答必须准确、克制、以客户问题解决为中心；当知识不足或涉及高风险承诺时，必须明确说明并转人工。',
    '["knowledge_base","handoff","conversation_log"]',
    'medium',
    TRUE
)
ON DUPLICATE KEY UPDATE name=VALUES(name), source_repo=VALUES(source_repo), source_path=VALUES(source_path);

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
INSERT INTO workers (name, category_id, avatar_icon, avatar_gradient_from, avatar_gradient_to, level, skills, description, hourly_rate, billing_unit, status, worker_type, delivery_mode, template_key, rating, total_orders) VALUES
('全栈架构师 #001', 1, 'mdi:code-braces', '#6366f1', '#9333ea', 9, 'React,Node.js,Go,Kubernetes,微服务', '精通前后端分离架构，擅长高并发系统设计，具备10万+QPS生产系统调优经验。支持React/Vue/Angular前端及Go/Java/Python后端开发。', 1.80, '时薪', 'online', 'general', 'manual_service', NULL, 4.9, 1842),
('Python全栈工程狮', 1, 'mdi:language-python', '#3b82f6', '#06b6d4', 8, 'Python,Django,FastAPI,PostgreSQL,Redis', '专注Python生态，从Web应用到数据管道全链路覆盖。熟练使用Django/FastAPI构建企业级应用，精通异步编程和性能优化。', 1.50, '时薪', 'online', 'general', 'manual_service', NULL, 4.8, 1256),
('移动端开发专家', 1, 'mdi:cellphone-link', '#8b5cf6', '#ec4899', 7, 'Flutter,React Native,iOS,Android,跨平台', '一套代码多端运行，精通Flutter与React Native跨平台开发。具备原生iOS/Android开发经验，确保最佳用户体验。', 2.00, '时薪', 'online', 'general', 'manual_service', NULL, 4.7, 893),
('Midjourney 原画师', 2, 'mdi:palette', '#ec4899', '#f43f5e', 7, '赛博朋克,写实风格,插画,概念设计', '精通多种AI绘画风格，擅长将抽象需求转化为视觉作品。单日可交付20+高质量原画，满足游戏、广告、品牌等多场景需求。', 0.50, '按件计费', 'online', 'general', 'manual_service', NULL, 4.8, 3210),
('UI/UX 动效大师', 2, 'mdi:animation-play', '#f59e0b', '#ef4444', 8, 'Figma,After Effects,Lottie,交互设计', '专注用户体验和界面动效设计，将静态页面转化为流畅的交互体验。熟练使用Figma设计系统，支持Lottie动画导出。', 2.20, '时薪', 'busy', 'general', 'manual_service', NULL, 4.9, 967),
('多语言客服 #12', 3, 'mdi:headphones', '#06b6d4', '#3b82f6', 8, '英语,日语,韩语,投诉处理,智能应答', '支持中英日韩四语实时对话，7×24小时不间断服务。内置情感分析引擎，智能识别客户情绪并调整应答策略，客户满意度4.9+。', 299.00, '月租', 'online', 'agent_service', 'managed_deployment', 'support_responder', 4.9, 2100),
('智能质检客服', 3, 'mdi:shield-check', '#10b981', '#059669', 6, '质量检测,话术优化,工单流转', '实时监控客服对话质量，自动识别违规话术和服务漏洞。支持对接主流工单系统，自动生成质检报告和改进建议。', 199.00, '月租', 'online', 'general', 'manual_service', NULL, 4.6, 580),
('金融分析师 Pro', 4, 'mdi:chart-areaspline', '#f59e0b', '#ea580c', 10, '波段分析,风险管理,量化策略,财报解读', '具备CFA级别的金融分析能力，擅长A股/美股/加密货币多市场分析。支持实时行情监控、风险预警和量化策略回测。', 5.20, '时薪', 'online', 'general', 'manual_service', NULL, 4.9, 756),
('短视频剪辑手', 5, 'mdi:movie-edit', '#ef4444', '#ec4899', 6, '爆款节奏,字幕生成,转场特效,多平台适配', '精通抖音/快手/B站等平台的爆款视频节奏。一键生成字幕、添加转场特效，支持竖屏/横屏多尺寸输出，日产量50+条。', 0.95, '时薪', 'online', 'general', 'manual_service', NULL, 4.5, 4320),
('法律文书合规官', 6, 'mdi:gavel', '#10b981', '#059669', 8, '合同审核,侵权检索,GDPR合规,知识产权', '基于最新法律数据库的智能合规审查，支持合同条款风险识别、知识产权侵权检索和GDPR合规检查。审核效率是人类律师的50倍。', 4.50, '时薪', 'online', 'general', 'manual_service', NULL, 4.8, 1120),
('SEO 增长黑客', 7, 'mdi:search-web', '#8b5cf6', '#d946ef', 5, '关键词策略,文章生成,外链建设,数据追踪', '全链路SEO优化方案，从关键词调研到内容生产到排名追踪一站式服务。支持Google/百度/Bing多搜索引擎优化。', 0.12, '按件计费', 'online', 'general', 'manual_service', NULL, 4.4, 6780),
('游戏数值策划师', 8, 'mdi:controller', '#0ea5e9', '#6366f1', 9, '概率模型,经济系统平衡,数值仿真,玩家行为分析', '精通游戏经济系统设计和数值平衡调优。基于蒙特卡洛模拟和玩家行为数据，确保游戏内经济不崩溃、数值不膨胀。', 3.20, '时薪', 'online', 'general', 'manual_service', NULL, 4.7, 432)
ON DUPLICATE KEY UPDATE name=name;

INSERT INTO service_plans (worker_id, slug, name, description, billing_cycle, price, currency, included_conversations, max_handoffs, channel_limit, seat_limit, default_duration_hours, is_active)
SELECT id, 'starter', 'Starter', '适合官网咨询与 FAQ 场景', 'monthly', 299.00, 'CNY', 500, 50, 1, 1, 720, TRUE
FROM workers WHERE name = '多语言客服 #12'
ON DUPLICATE KEY UPDATE name=VALUES(name), description=VALUES(description), price=VALUES(price);

INSERT INTO service_plans (worker_id, slug, name, description, billing_cycle, price, currency, included_conversations, max_handoffs, channel_limit, seat_limit, default_duration_hours, is_active)
SELECT id, 'pro', 'Pro', '适合已有客服团队的企业', 'monthly', 699.00, 'CNY', 2000, 200, 3, 3, 720, TRUE
FROM workers WHERE name = '多语言客服 #12'
ON DUPLICATE KEY UPDATE name=VALUES(name), description=VALUES(description), price=VALUES(price);

INSERT INTO service_plans (worker_id, slug, name, description, billing_cycle, price, currency, included_conversations, max_handoffs, channel_limit, seat_limit, default_duration_hours, is_active)
SELECT id, 'enterprise', 'Enterprise', '适合多渠道与深度协同场景', 'monthly', 1499.00, 'CNY', 10000, 1000, 10, 10, 720, TRUE
FROM workers WHERE name = '多语言客服 #12'
ON DUPLICATE KEY UPDATE name=VALUES(name), description=VALUES(description), price=VALUES(price);
