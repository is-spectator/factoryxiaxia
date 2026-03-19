"""虾虾工厂 — Flask 应用入口

本文件负责：
1) 创建 Flask app 实例
2) 初始化扩展 (db, limiter, CORS)
3) 注册蓝图 (routes/*)
4) 启动时执行轻量 schema 迁移与底座数据初始化

注意：
- 数据模型在 models.py
- 路由在 routes/
"""

import os
import datetime

from flask import Flask, request, jsonify, g
from flask_cors import CORS

from sqlalchemy import inspect, text

from extensions import db, limiter
from utils.helpers import JsonFormatter, setup_logging, send_alert

from routes.auth import bp as auth_bp
from routes.catalog import bp as catalog_bp
from routes.chat import bp as chat_bp
from routes.deployments import bp as deployments_bp
from routes.orders import bp as orders_bp
from routes.admin import bp as admin_bp
from routes.system import bp as system_bp
from models import (
    AgentTemplate,
    AuditLog,
    Category,
    ConversationMessage,
    ConversationSession,
    Deployment,
    Favorite,
    HandoffTicket,
    KnowledgeBase,
    KnowledgeDocument,
    Message,
    Order,
    Organization,
    Payment,
    Review,
    ServicePlan,
    User,
    UsageRecord,
    Worker,
)
from services.deployment_service import ensure_public_token

logger = setup_logging()

app = Flask(__name__)
CORS(app)

DB_USER = os.environ.get("DB_USER", "xiaxia")
DB_PASS = os.environ.get("DB_PASS", "xiaxia_secret_2026")
DB_HOST = os.environ.get("DB_HOST", "db")
DB_NAME = os.environ.get("DB_NAME", "xiaxia_factory")

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?charset=utf8mb4"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
limiter.init_app(app)
limiter._default_limits = [os.environ.get("RATE_LIMIT_DEFAULT", "60/minute")]


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    duration = ""
    if hasattr(g, "request_start"):
        duration = f" {(datetime.datetime.utcnow() - g.request_start).total_seconds() * 1000:.0f}ms"
    logger.info(f"{request.method} {request.path} → {response.status_code}{duration}")
    return response


@app.before_request
def before_request_hook():
    g.request_start = datetime.datetime.utcnow()


@app.errorhandler(500)
def handle_500(e):
    logger.error(f"Internal Server Error: {e}", exc_info=True)
    send_alert("500 Internal Server Error", f"{request.method} {request.path}\n{e}")
    return jsonify({"error": "服务器内部错误"}), 500


@app.errorhandler(429)
def handle_429(e):
    return jsonify({"error": "请求过于频繁，请稍后再试"}), 429


def ensure_column(table_name, column_name, column_sql):
    inspector = inspect(db.engine)
    if table_name not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name in existing_columns:
        return

    with db.engine.begin() as conn:
        conn.execute(db.text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"))
    logger.info("Applied startup schema migration: added %s.%s", table_name, column_name)


def ensure_foundation_schema():
    ensure_column("orders", "activated_at", "DATETIME NULL")
    ensure_column("workers", "worker_type", "VARCHAR(30) DEFAULT 'general'")
    ensure_column("workers", "delivery_mode", "VARCHAR(30) DEFAULT 'manual_service'")
    ensure_column("workers", "template_key", "VARCHAR(80) NULL")
    ensure_column("orders", "order_type", "VARCHAR(30) DEFAULT 'rental'")
    ensure_column("orders", "service_plan_id", "INTEGER NULL")
    ensure_column("deployments", "public_token", "VARCHAR(120) NULL")


def ensure_order_schema():
    """兼容旧测试名，保留 orders 相关补列逻辑。"""
    ensure_foundation_schema()


def bootstrap_agent_foundation():
    templates = [
        {
            "key": "support_responder",
            "name": "Support Responder",
            "source_repo": "https://github.com/msitarzewski/agency-agents",
            "source_path": "support/support-support-responder.md",
            "prompt_template": (
                "你是企业专属数字客服员工，负责基于知识库进行客户问答、问题澄清、"
                "工单分流与转人工判断。回答必须准确、克制、以客户问题解决为中心；"
                "当知识不足或涉及高风险承诺时，必须明确说明并转人工。"
            ),
            "default_tools": '["knowledge_base","handoff","conversation_log"]',
            "risk_level": "medium",
        },
        {
            "key": "wechat_official_account_manager",
            "name": "WeChat Official Account Manager",
            "source_repo": "https://github.com/msitarzewski/agency-agents",
            "source_path": "marketing/marketing-wechat-official-account.md",
            "prompt_template": (
                "你是企业专属微信公众号数字运营员工，负责根据品牌资料输出内容选题、"
                "自动回复策略、菜单架构建议与用户转化话术。回答必须贴合微信生态和私域运营场景，"
                "遇到高风险承诺、投放违规或知识不足时必须谨慎并建议人工确认。"
            ),
            "default_tools": '["knowledge_base","conversation_log","content_calendar"]',
            "risk_level": "medium",
        },
    ]
    template_map = {}
    for template_data in templates:
        template = AgentTemplate.query.filter_by(key=template_data["key"]).first()
        if not template:
            template = AgentTemplate(
                key=template_data["key"],
                name=template_data["name"],
                source_repo=template_data["source_repo"],
                source_path=template_data["source_path"],
                prompt_template=template_data["prompt_template"],
                default_tools=template_data["default_tools"],
                risk_level=template_data["risk_level"],
                is_active=True,
            )
            db.session.add(template)
            db.session.flush()
        else:
            template.name = template_data["name"]
            template.source_repo = template_data["source_repo"]
            template.source_path = template_data["source_path"]
            template.prompt_template = template_data["prompt_template"]
            template.default_tools = template_data["default_tools"]
            template.risk_level = template_data["risk_level"]
            template.is_active = True
        template_map[template.key] = template

    categories = {
        "智能客服": {"icon": "mdi:headphones", "description": "多语言客服、投诉处理、智能应答", "sort_order": 3},
        "营销推广": {"icon": "mdi:search-web", "description": "SEO优化、广告投放、增长黑客", "sort_order": 7},
    }
    for category_name, category_data in categories.items():
        category = Category.query.filter_by(name=category_name).first()
        if not category:
            category = Category(
                name=category_name,
                icon=category_data["icon"],
                description=category_data["description"],
                sort_order=category_data["sort_order"],
            )
            db.session.add(category)
            db.session.flush()

    official_workers = [
        {
            "name": "多语言客服 #12",
            "category_name": "智能客服",
            "avatar_icon": "mdi:headphones",
            "avatar_gradient_from": "#06b6d4",
            "avatar_gradient_to": "#3b82f6",
            "level": 8,
            "skills": "英语,日语,韩语,投诉处理,智能应答",
            "description": "支持中英日韩四语实时对话，7x24 小时在线处理 FAQ、咨询接待与复杂问题转人工。",
            "hourly_rate": 299.00,
            "billing_unit": "月租",
            "template_key": "support_responder",
            "plans": [
                {
                    "slug": "starter",
                    "name": "Starter",
                    "description": "适合官网咨询与 FAQ 场景",
                    "price": 299.00,
                    "included_conversations": 500,
                    "max_handoffs": 50,
                    "channel_limit": 1,
                    "seat_limit": 1,
                },
                {
                    "slug": "pro",
                    "name": "Pro",
                    "description": "适合已有客服团队的企业",
                    "price": 699.00,
                    "included_conversations": 2000,
                    "max_handoffs": 200,
                    "channel_limit": 3,
                    "seat_limit": 3,
                },
                {
                    "slug": "enterprise",
                    "name": "Enterprise",
                    "description": "适合多渠道与深度协同场景",
                    "price": 1499.00,
                    "included_conversations": 10000,
                    "max_handoffs": 1000,
                    "channel_limit": 10,
                    "seat_limit": 10,
                },
            ],
        },
        {
            "name": "公众号运营官 #18",
            "category_name": "营销推广",
            "avatar_icon": "mdi:wechat",
            "avatar_gradient_from": "#10b981",
            "avatar_gradient_to": "#22c55e",
            "level": 7,
            "skills": "微信公众号,自动回复,菜单架构,内容规划,粉丝转化",
            "description": "专注微信公众号内容运营、自动回复策略、菜单架构和粉丝转化，适合品牌私域与内容增长场景。",
            "hourly_rate": 399.00,
            "billing_unit": "月租",
            "template_key": "wechat_official_account_manager",
            "plans": [
                {
                    "slug": "starter",
                    "name": "Starter",
                    "description": "适合单账号运营与基础自动回复",
                    "price": 399.00,
                    "included_conversations": 800,
                    "max_handoffs": 30,
                    "channel_limit": 1,
                    "seat_limit": 1,
                },
                {
                    "slug": "pro",
                    "name": "Pro",
                    "description": "适合内容团队协同与粉丝增长",
                    "price": 899.00,
                    "included_conversations": 3000,
                    "max_handoffs": 100,
                    "channel_limit": 2,
                    "seat_limit": 3,
                },
                {
                    "slug": "enterprise",
                    "name": "Enterprise",
                    "description": "适合多矩阵账号与复杂私域运营",
                    "price": 1999.00,
                    "included_conversations": 12000,
                    "max_handoffs": 300,
                    "channel_limit": 5,
                    "seat_limit": 8,
                },
            ],
        },
    ]
    for worker_data in official_workers:
        category = Category.query.filter_by(name=worker_data["category_name"]).first()
        worker = Worker.query.filter_by(name=worker_data["name"]).first()
        if not worker:
            worker = Worker(
                name=worker_data["name"],
                category_id=category.id,
                avatar_icon=worker_data["avatar_icon"],
                avatar_gradient_from=worker_data["avatar_gradient_from"],
                avatar_gradient_to=worker_data["avatar_gradient_to"],
                level=worker_data["level"],
                skills=worker_data["skills"],
                description=worker_data["description"],
                hourly_rate=worker_data["hourly_rate"],
                billing_unit=worker_data["billing_unit"],
                status="online",
                worker_type="agent_service",
                delivery_mode="managed_deployment",
                template_key=worker_data["template_key"],
                rating=4.9,
                total_orders=worker.total_orders if worker else 0,
            )
            db.session.add(worker)
            db.session.flush()
        else:
            worker.category_id = category.id
            worker.avatar_icon = worker_data["avatar_icon"]
            worker.avatar_gradient_from = worker_data["avatar_gradient_from"]
            worker.avatar_gradient_to = worker_data["avatar_gradient_to"]
            worker.level = worker_data["level"]
            worker.skills = worker_data["skills"]
            worker.description = worker_data["description"]
            worker.hourly_rate = worker_data["hourly_rate"]
            worker.billing_unit = worker_data["billing_unit"]
            worker.status = "online"
            worker.worker_type = "agent_service"
            worker.delivery_mode = "managed_deployment"
            worker.template_key = worker_data["template_key"]

        existing_plans = {
            plan.slug: plan for plan in ServicePlan.query.filter_by(worker_id=worker.id).all()
        }
        for plan_data in worker_data["plans"]:
            plan = existing_plans.get(plan_data["slug"])
            if not plan:
                plan = ServicePlan(worker_id=worker.id, slug=plan_data["slug"])
                db.session.add(plan)
            plan.name = plan_data["name"]
            plan.description = plan_data["description"]
            plan.billing_cycle = "monthly"
            plan.price = plan_data["price"]
            plan.currency = "CNY"
            plan.included_conversations = plan_data["included_conversations"]
            plan.max_handoffs = plan_data["max_handoffs"]
            plan.channel_limit = plan_data["channel_limit"]
            plan.seat_limit = plan_data["seat_limit"]
            plan.default_duration_hours = 720
            plan.is_active = True

    logger.info("Bootstrapped official agent offerings")

    for deployment in Deployment.query.filter(
        Deployment.status == "active",
        db.or_(Deployment.public_token.is_(None), Deployment.public_token == "")
    ).all():
        ensure_public_token(deployment)


app.register_blueprint(auth_bp)
app.register_blueprint(catalog_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(deployments_bp)
app.register_blueprint(orders_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(system_bp)


with app.app_context():
    db.create_all()
    ensure_foundation_schema()
    bootstrap_agent_foundation()
    db.session.commit()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
