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


def ensure_order_schema():
    """兼容旧测试名，保留 orders 相关补列逻辑。"""
    ensure_foundation_schema()


def bootstrap_agent_foundation():
    template = AgentTemplate.query.filter_by(key="support_responder").first()
    if not template:
        template = AgentTemplate(
            key="support_responder",
            name="Support Responder",
            source_repo="https://github.com/msitarzewski/agency-agents",
            source_path="support/support-support-responder.md",
            prompt_template=(
                "你是企业专属数字客服员工，负责基于知识库进行客户问答、问题澄清、"
                "工单分流与转人工判断。回答必须准确、克制、以客户问题解决为中心；"
                "当知识不足或涉及高风险承诺时，必须明确说明并转人工。"
            ),
            default_tools='["knowledge_base","handoff","conversation_log"]',
            risk_level="medium",
            is_active=True,
        )
        db.session.add(template)
        db.session.flush()

    worker = Worker.query.filter_by(name="多语言客服 #12").first()
    if worker:
        changed = False
        if worker.worker_type != "agent_service":
            worker.worker_type = "agent_service"
            changed = True
        if worker.delivery_mode != "managed_deployment":
            worker.delivery_mode = "managed_deployment"
            changed = True
        if worker.template_key != template.key:
            worker.template_key = template.key
            changed = True

        existing_plan_slugs = {
            plan.slug for plan in ServicePlan.query.filter_by(worker_id=worker.id).all()
        }
        default_plans = [
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
        ]
        for plan in default_plans:
            if plan["slug"] in existing_plan_slugs:
                continue
            db.session.add(ServicePlan(
                worker_id=worker.id,
                slug=plan["slug"],
                name=plan["name"],
                description=plan["description"],
                billing_cycle="monthly",
                price=plan["price"],
                included_conversations=plan["included_conversations"],
                max_handoffs=plan["max_handoffs"],
                channel_limit=plan["channel_limit"],
                seat_limit=plan["seat_limit"],
                default_duration_hours=720,
                is_active=True,
            ))
            changed = True

        if changed:
            logger.info("Bootstrapped support responder worker foundation")


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
