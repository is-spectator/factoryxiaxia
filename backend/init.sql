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
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (worker_id) REFERENCES workers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
