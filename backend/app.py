"""虾虾工厂 — Flask 应用入口

本文件仅负责：
1. 创建 Flask app 实例
2. 初始化扩展 (db, limiter, CORS)
3. 注册蓝图 (routes/*)
4. 设置中间件 (安全头, 日志, 异常处理)

业务逻辑已拆分至:
- models.py        — 数据模型
- extensions.py    — Flask 扩展实例
- utils/auth.py    — JWT / 认证
- utils/helpers.py — 通用工具
- services/        — 业务服务
- routes/          — 路由蓝图
"""
import os
import datetime

from flask import Flask, request, jsonify, g
from flask_cors import CORS

from extensions import db, limiter
from utils.helpers import setup_logging, send_alert

# ===== 日志 =====
logger = setup_logging()

# ===== Flask 应用 =====
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

# ===== 初始化扩展 =====
db.init_app(app)
limiter.init_app(app)

# ===== 中间件 =====


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    duration = ""
    if hasattr(g, "request_start"):
        duration = f" {(datetime.datetime.utcnow() - g.request_start).total_seconds()*1000:.0f}ms"
    logger.info(f"{request.method} {request.path} → {response.status_code}{duration}")
    return response


@app.before_request
def before_request_hook():
    g.request_start = datetime.datetime.utcnow()


# ===== 异常处理 =====


@app.errorhandler(500)
def handle_500(e):
    logger.error(f"Internal Server Error: {e}", exc_info=True)
    send_alert("500 Internal Server Error", f"{request.method} {request.path}\n{e}")
    return jsonify({"error": "服务器内部错误"}), 500


@app.errorhandler(429)
def handle_429(e):
    return jsonify({"error": "请求过于频繁，请稍后再试"}), 429


# ===== 注册蓝图 =====
from routes.auth import bp as auth_bp          # noqa: E402
from routes.catalog import bp as catalog_bp    # noqa: E402
from routes.orders import bp as orders_bp      # noqa: E402
from routes.admin import bp as admin_bp        # noqa: E402
from routes.system import bp as system_bp      # noqa: E402

app.register_blueprint(auth_bp)
app.register_blueprint(catalog_bp)
app.register_blueprint(orders_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(system_bp)

# ===== 向后兼容：让测试可以 import app 后访问模型和工具 =====
from models import (  # noqa: E402, F401
    User, Category, Worker, Order, Payment, Review, Message, Favorite,
    ROLES, ORDER_STATUSES, ORDER_TRANSITIONS,
)
from utils.auth import (  # noqa: E402, F401
    create_token, verify_token, get_current_user, require_admin,
)
from utils.helpers import (  # noqa: E402, F401
    generate_order_no, generate_payment_no, EMAIL_RE, JsonFormatter,
)
from services.messages import send_message  # noqa: E402, F401

# ===== 建表 =====
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
