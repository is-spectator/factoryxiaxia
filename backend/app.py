"""虾虾工厂 — Flask 应用入口

本文件负责：
1) 创建 Flask app 实例
2) 初始化扩展 (db, limiter, CORS)
3) 注册蓝图 (routes/*)
4) 启动时执行轻量 schema 迁移（确保 activated_at 存在）

注意：
- 数据模型在 models.py
- 路由在 routes/
"""

import os
import datetime

from flask import Flask, request, jsonify, g
from flask_cors import CORS

from sqlalchemy import inspect

from extensions import db, limiter
from utils.helpers import setup_logging, send_alert

from routes.auth import bp as auth_bp
from routes.catalog import bp as catalog_bp
from routes.orders import bp as orders_bp
from routes.admin import bp as admin_bp
from routes.system import bp as system_bp
from routes.deployments import bp as deployments_bp
from routes.chat import bp as chat_bp

# Re-export models and utilities for test access (app_module.User, etc.)
from models import User, Category, Worker  # noqa: F401
from sqlalchemy import text  # noqa: F401
from utils.helpers import JsonFormatter  # noqa: F401

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


def ensure_order_schema():
    inspector = inspect(db.engine)
    if "orders" not in inspector.get_table_names():
        return

    order_columns = {column["name"] for column in inspector.get_columns("orders")}
    if "activated_at" in order_columns:
        return

    alter_sql = "ALTER TABLE orders ADD COLUMN activated_at DATETIME NULL"
    if db.engine.dialect.name == "mysql":
        alter_sql += " AFTER paid_at"

    with db.engine.begin() as conn:
        conn.execute(db.text(alter_sql))
    logger.info("Applied startup schema migration: added orders.activated_at")


app.register_blueprint(auth_bp)
app.register_blueprint(catalog_bp)
app.register_blueprint(orders_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(system_bp)
app.register_blueprint(deployments_bp)
app.register_blueprint(chat_bp)


with app.app_context():
    db.create_all()
    ensure_order_schema()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
